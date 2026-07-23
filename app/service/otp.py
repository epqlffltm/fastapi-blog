#app/service/otp.py

'''
2026-07-23
OTP 서비스 (생성 / Redis 임시 저장 / 검증)
'''

import random
from fastapi import Depends
from redis import Redis
from ..database.cache import get_redis_client


class OTPService:
    ttl: int = 3 * 60          # 3분 후 자동 삭제
    purpose: str = "signup"    # 용도별로 키를 분리 (가입 인증 / 비번 재설정)

    def __init__(self, redis: Redis = Depends(get_redis_client)):
        self.redis = redis

    def _key(self, email: str) -> str:
        return f"otp:{self.purpose}:{email}"

    @staticmethod
    def create_otp() -> int:
        # 6자리 (앞자리 0 방지)
        return random.randint(100_000, 999_999)

    def save_otp(self, email: str, otp: int) -> None:
        # ex=ttl → 만료 처리를 Redis가 대신한다
        self.redis.set(self._key(email), otp, ex=self.ttl)

    def get_otp(self, email: str) -> int | None:
        value = self.redis.get(self._key(email))
        return int(value) if value is not None else None

    def delete_otp(self, email: str) -> None:
        self.redis.delete(self._key(email))