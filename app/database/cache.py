#app/database/cache.py

'''
2026-07-23
Redis 연결 (OTP 임시 저장용)
'''

from redis import Redis
from .connection import settings

redis_client = Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    encoding="UTF-8",
    decode_responses=True,   # bytes 대신 str로 받는다
)


def get_redis_client() -> Redis:
    return redis_client