"""인증된 사용자의 글·댓글 생성 빈도를 Redis에서 제한한다."""

import logging
from dataclasses import dataclass

from fastapi import Depends
from redis.asyncio import Redis

from ..database.cache import get_redis_client
from ..database.connection import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int


class ContentWriteRateLimitService:
    """사용자 ID 기준 고정 구간 레이트리밋.

    글과 댓글은 인증 후에만 생성할 수 있으므로 IP가 아니라 사용자 ID를
    주 키로 쓴다. Redis 장애 시에는 로그인 레이트리밋과 같은 정책으로
    fail-open하고 예외 로그를 남긴다.
    """

    def __init__(self, redis: Redis = Depends(get_redis_client)):
        self.redis = redis

    async def consume_post(self, user_id: int) -> RateLimitDecision:
        return await self._consume(
            action="post-create",
            user_id=user_id,
            max_requests=settings.post_create_limit,
            window_seconds=settings.post_create_window_seconds,
        )

    async def consume_comment(self, user_id: int) -> RateLimitDecision:
        return await self._consume(
            action="comment-create",
            user_id=user_id,
            max_requests=settings.comment_create_limit,
            window_seconds=settings.comment_create_window_seconds,
        )

    @staticmethod
    def _key(action: str, user_id: int) -> str:
        return f"write-rate:{action}:user:{user_id}"

    async def _consume(
        self,
        *,
        action: str,
        user_id: int,
        max_requests: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        # INCR와 최초 EXPIRE를 한 스크립트로 묶어 만료 없는 키가 남지 않게 한다.
        # max_requests번째 요청까지 허용하고 그 다음 요청부터 막는다.
        script = """
        -- CONTENT_WRITE_RATE_LIMIT
        local count = redis.call("INCR", KEYS[1])
        local window = tonumber(ARGV[1])
        local max_requests = tonumber(ARGV[2])

        if count == 1 then
            redis.call("EXPIRE", KEYS[1], window)
        end

        local ttl = redis.call("TTL", KEYS[1])
        if ttl < 0 then
            redis.call("EXPIRE", KEYS[1], window)
            ttl = window
        end

        if count > max_requests then
            return {0, ttl}
        end
        return {1, ttl}
        """

        try:
            raw_allowed, raw_ttl = await self.redis.eval(
                script,
                1,
                self._key(action, user_id),
                window_seconds,
                max_requests,
            )
        except Exception:
            logger.exception(
                "content write rate limit failed; allowing request",
                extra={"action": action, "user_id": user_id},
            )
            return RateLimitDecision(allowed=True, retry_after=0)

        return RateLimitDecision(
            allowed=int(raw_allowed) == 1,
            retry_after=max(0, int(raw_ttl)),
        )
