#app/service/otp.py

'''
2026-07-23
OTP 서비스 (생성 / Redis 임시 저장 / 검증)

2026-07-24
재발급 제한 추가
용도(purpose)를 인자로 받도록 변경 (signup / reset)

2026-07-28
Redis 비동기 전환
OTP 검증 횟수 제한 / 검증 성공 시 원자적 소비
'''

import secrets
from enum import IntEnum

from fastapi import Depends
from redis.asyncio import Redis

from ..database.cache import get_redis_client


class OTPVerifyResult(IntEnum):
    """Redis Lua 검증 스크립트의 명시적인 결과 코드."""

    VERIFIED = 1
    INVALID = 0
    EXPIRED_OR_MISSING = -1
    TOO_MANY_ATTEMPTS = -2


class OTPService:
    ttl: int = 3 * 60
    cooldown: int = 60
    send_window: int = 60 * 60
    max_sends: int = 5
    max_verify_attempts: int = 5

    def __init__(self, redis: Redis = Depends(get_redis_client)):
        self.redis = redis

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    def _key(self, email: str, purpose: str) -> str:
        return f"otp:{purpose}:{self._normalize_email(email)}"

    def _cooldown_key(self, email: str, purpose: str) -> str:
        return f"otp:cooldown:{purpose}:{self._normalize_email(email)}"

    def _send_count_key(self, email: str, purpose: str) -> str:
        return f"otp:send-count:{purpose}:{self._normalize_email(email)}"

    def _verify_attempt_key(self, email: str, purpose: str) -> str:
        return f"otp:verify-attempts:{purpose}:{self._normalize_email(email)}"

    @staticmethod
    def create_otp() -> int:
        return secrets.randbelow(900_000) + 100_000

    async def acquire_send_slot(self, email: str, purpose: str) -> bool:
        """1분 쿨다운과 1시간 최대 발송 횟수를 원자적으로 확인·등록한다."""
        script = """
        -- OTP_ACQUIRE_SEND_SLOT
        local cooldown_key = KEYS[1]
        local count_key = KEYS[2]
        local cooldown_seconds = tonumber(ARGV[1])
        local window_seconds = tonumber(ARGV[2])
        local max_sends = tonumber(ARGV[3])

        if redis.call("EXISTS", cooldown_key) == 1 then
            return 0
        end

        local current_count = tonumber(redis.call("GET", count_key) or "0")
        if current_count >= max_sends then
            return 0
        end

        redis.call("SET", cooldown_key, "1", "EX", cooldown_seconds)
        local new_count = redis.call("INCR", count_key)
        if new_count == 1 then
            redis.call("EXPIRE", count_key, window_seconds)
        end
        return 1
        """

        result = await self.redis.eval(
            script,
            2,
            self._cooldown_key(email, purpose),
            self._send_count_key(email, purpose),
            self.cooldown,
            self.send_window,
            self.max_sends,
        )
        return result == 1

    async def start_cooldown(self, email: str, purpose: str) -> bool:
        return await self.acquire_send_slot(email=email, purpose=purpose)

    async def save_otp(self, email: str, otp: int, purpose: str) -> None:
        """새 OTP를 저장하고 이전 코드의 검증 실패 횟수를 함께 초기화한다."""
        script = """
        -- OTP_SAVE_AND_RESET_ATTEMPTS
        redis.call("SET", KEYS[1], ARGV[1], "EX", tonumber(ARGV[2]))
        redis.call("DEL", KEYS[2])
        return 1
        """
        await self.redis.eval(
            script,
            2,
            self._key(email, purpose),
            self._verify_attempt_key(email, purpose),
            str(otp),
            self.ttl,
        )

    async def verify_and_consume(
        self,
        email: str,
        otp: int,
        purpose: str,
    ) -> OTPVerifyResult:
        """검증 횟수를 제한하고 성공한 OTP를 한 Lua 실행 안에서 소비한다."""
        script = """
        -- OTP_VERIFY_AND_CONSUME
        local otp_key = KEYS[1]
        local attempts_key = KEYS[2]
        local provided_otp = ARGV[1]
        local max_attempts = tonumber(ARGV[2])
        local fallback_ttl_seconds = tonumber(ARGV[3])

        local attempts = tonumber(redis.call("GET", attempts_key) or "0")
        if attempts >= max_attempts then
            return -2
        end

        local saved_otp = redis.call("GET", otp_key)
        if not saved_otp then
            redis.call("DEL", attempts_key)
            return -1
        end

        if saved_otp == provided_otp then
            redis.call("DEL", otp_key)
            redis.call("DEL", attempts_key)
            return 1
        end

        local remaining_ttl_ms = redis.call("PTTL", otp_key)
        local new_attempts = redis.call("INCR", attempts_key)
        if new_attempts == 1 then
            if remaining_ttl_ms > 0 then
                redis.call("PEXPIRE", attempts_key, remaining_ttl_ms)
            else
                redis.call("EXPIRE", attempts_key, fallback_ttl_seconds)
            end
        end

        if new_attempts >= max_attempts then
            redis.call("DEL", otp_key)
            return -2
        end
        return 0
        """

        raw_result = await self.redis.eval(
            script,
            2,
            self._key(email, purpose),
            self._verify_attempt_key(email, purpose),
            str(otp),
            self.max_verify_attempts,
            self.ttl,
        )
        try:
            return OTPVerifyResult(int(raw_result))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"unexpected OTP verification result: {raw_result!r}") from exc

    async def get_otp(self, email: str, purpose: str) -> int | None:
        value = await self.redis.get(self._key(email, purpose))
        return int(value) if value is not None else None

    async def delete_otp(self, email: str, purpose: str) -> None:
        await self.redis.delete(
            self._key(email, purpose),
            self._verify_attempt_key(email, purpose),
        )
