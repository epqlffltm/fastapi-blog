#app/service/otp.py

'''
2026-07-23
OTP 서비스 (생성 / Redis 임시 저장 / 검증)

2024-07-24
재발급 제한 추가
용도(purpose)를 인자로 받도록 변경 (signup / reset)
'''

import random
from fastapi import Depends
from redis import Redis
from ..database.cache import get_redis_client


class OTPService:
    ttl: int = 3 * 60          # 3분 후 자동 삭제
    cooldown: int = 60         # 재발급 제한 (1분)

    def __init__(self, redis: Redis = Depends(get_redis_client)):
        self.redis = redis

    def _key(self, email: str, purpose: str) -> str:
        # 용도별로 키를 분리해야 가입 코드로 비번을 못 바꾼다
        return f"otp:{purpose}:{email}"

    def _cooldown_key(self, email: str, purpose: str) -> str:
        return f"otp:cooldown:{purpose}:{email}"

    @staticmethod
    def create_otp() -> int:
        # 6자리 (앞자리 0 방지)
        return random.randint(100_000, 999_999)

    def start_cooldown(self, email: str, purpose: str) -> bool:
        """제한을 걸면서 동시에 통과 여부를 반환. 이미 걸려 있으면 False."""
        # nx=True → 키가 없을 때만 저장. 확인과 저장이 한 번에 일어나 경쟁 상태가 없다
        return bool(
            self.redis.set(
                self._cooldown_key(email, purpose), 1, ex=self.cooldown, nx=True
            )
        )

    def save_otp(self, email: str, otp: int, purpose: str) -> None:
        # ex=ttl → 만료 처리를 Redis가 대신한다
        self.redis.set(self._key(email, purpose), otp, ex=self.ttl)

    def get_otp(self, email: str, purpose: str) -> int | None:
        value = self.redis.get(self._key(email, purpose))
        return int(value) if value is not None else None

    def delete_otp(self, email: str, purpose: str) -> None:
        self.redis.delete(self._key(email, purpose))