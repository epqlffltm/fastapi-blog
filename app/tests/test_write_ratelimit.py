import pytest

from app.service.write_ratelimit import ContentWriteRateLimitService


@pytest.mark.asyncio
async def test_post_rate_limit_allows_request(mock_redis):
    mock_redis.eval.return_value = [1, 600]
    service = ContentWriteRateLimitService(redis=mock_redis)

    decision = await service.consume_post(user_id=7)

    assert decision.allowed is True
    assert decision.retry_after == 600
    args = mock_redis.eval.await_args.args
    assert args[2] == "write-rate:post-create:user:7"


@pytest.mark.asyncio
async def test_comment_rate_limit_blocks_request(mock_redis):
    mock_redis.eval.return_value = [0, 23]
    service = ContentWriteRateLimitService(redis=mock_redis)

    decision = await service.consume_comment(user_id=9)

    assert decision.allowed is False
    assert decision.retry_after == 23
    args = mock_redis.eval.await_args.args
    assert args[2] == "write-rate:comment-create:user:9"


@pytest.mark.asyncio
async def test_content_rate_limit_fails_open_when_redis_is_down(mock_redis):
    mock_redis.eval.side_effect = ConnectionError("redis down")
    service = ContentWriteRateLimitService(redis=mock_redis)

    decision = await service.consume_post(user_id=1)

    assert decision.allowed is True
    assert decision.retry_after == 0
