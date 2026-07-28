#app/service/otp.py

'''
2026-07-23
OTP 서비스 (생성 / Redis 임시 저장 / 검증)

2026-07-24
재발급 제한 추가
용도(purpose)를 인자로 받도록 변경 (signup / reset)

2026-07-28
Redis 비동기 전환
'''

import secrets

from fastapi import Depends
from redis.asyncio import Redis

from ..database.cache import get_redis_client


class OTPService:
    ttl: int = 3 * 60           # 3분 후 자동 삭제
    cooldown: int = 60          # 연속 발송 제한 (1분)
    send_window: int = 60 * 60  # 발송 횟수 집계 구간 (1시간)
    max_sends: int = 5          # 이메일·용도별 1시간 최대 발송 횟수

    def __init__(self, redis: Redis = Depends(get_redis_client)):
        self.redis = redis

    def _key(self, email: str, purpose: str) -> str:
        # 용도별로 키를 분리해야 가입 코드로 비번을 못 바꾼다
        return f"otp:{purpose}:{email}"

    def _cooldown_key(self, email: str, purpose: str) -> str:
        return f"otp:cooldown:{purpose}:{email}"

    def _send_count_key(self, email: str, purpose: str) -> str:
        return f"otp:send-count:{purpose}:{email}"

    @staticmethod
    def create_otp() -> int:
        # 암호학적으로 안전한 난수로 100000~999999 범위의 코드를 만든다
        return secrets.randbelow(900_000) + 100_000

    async def acquire_send_slot(self, email: str, purpose: str) -> bool:
        """1분 쿨다운과 1시간 최대 발송 횟수를 원자적으로 확인·등록한다."""
        script = """
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
        """기존 호출부 호환용."""
        return await self.acquire_send_slot(
            email=email,
            purpose=purpose,
        )

    async def save_otp(
        self,
        email: str,
        otp: int,
        purpose: str,
    ) -> None:
        await self.redis.set(
            self._key(email, purpose),
            otp,
            ex=self.ttl,
        )

    async def get_otp(
        self,
        email: str,
        purpose: str,
    ) -> int | None:
        value = await self.redis.get(self._key(email, purpose))
        return int(value) if value is not None else None

    async def delete_otp(
        self,
        email: str,
        purpose: str,
    ) -> None:
        await self.redis.delete(self._key(email, purpose))