#app/database/cache.py

'''
2026-07-23
Redis 연결 (OTP 임시 저장용)

2026-07-28
비동기 Redis 클라이언트로 전환
'''

from redis.asyncio import Redis

from .connection import settings


# 애플리케이션 전체에서 연결 풀 하나를 공유한다.
# redis.asyncio 명령은 호출부에서 await 해야 한다.
redis_client = Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    encoding="UTF-8",
    decode_responses=True,   # bytes 대신 str로 받는다
)


def get_redis_client() -> Redis:
    return redis_client


async def close_redis_client() -> None:
    """애플리케이션 종료 시 Redis 연결 풀을 정리한다."""
    await redis_client.aclose()