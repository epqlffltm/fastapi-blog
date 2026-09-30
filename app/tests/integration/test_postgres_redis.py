"""실제 PostgreSQL·Redis를 사용하는 보안 통합 테스트."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database.orm import Category, Comment, Post, User
from app.database.profile_repository import ProfileCommentRepository
from app.database.repository import UserRepository
from app.schema.request import LogInRequest, SignUpRequest
from app.service.otp import OTPService, OTPVerifyResult
from app.service.ratelimit import LoginRateLimitService

pytestmark = pytest.mark.integration


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return value


def _redis_url() -> str:
    value = os.getenv("TEST_REDIS_URL")
    if not value:
        pytest.skip("TEST_REDIS_URL is not configured")
    return value


@pytest.mark.asyncio
async def test_postgres_migration_and_deleted_post_comment_visibility():
    engine = create_async_engine(_database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as connection:
            token_version = await connection.scalar(
                text(
                    """
                    SELECT is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'users'
                      AND column_name = 'token_version'
                    """
                )
            )
            assert token_version == "NO"
            await connection.execute(
                text(
                    "TRUNCATE TABLE likes, comments, uploads, posts, categories, users "
                    "RESTART IDENTITY CASCADE"
                )
            )

        now = datetime.now(UTC)
        async with session_factory() as session:
            user = User.create(
                email="integration@example.com",
                hashed_password="$2b$12$integration",
                nickname="integration",
            )
            user.is_verified = True
            category = Category(slug="integration", name="통합", display_order=0)
            session.add_all((user, category))
            await session.flush()

            visible_post = Post(
                user_id=user.id,
                category_id=category.id,
                created_at=now,
                updated_at=now,
                title="visible",
                contents="visible",
                is_deleted=False,
                view_count=0,
            )
            deleted_post = Post(
                user_id=user.id,
                category_id=category.id,
                created_at=now,
                updated_at=now,
                title="deleted",
                contents="deleted",
                is_deleted=True,
                view_count=0,
            )
            session.add_all((visible_post, deleted_post))
            await session.flush()

            session.add_all(
                (
                    Comment(
                        post_id=visible_post.id,
                        user_id=user.id,
                        created_at=now,
                        updated_at=now,
                        contents="visible comment",
                        is_deleted=False,
                    ),
                    Comment(
                        post_id=deleted_post.id,
                        user_id=user.id,
                        created_at=now,
                        updated_at=now,
                        contents="must not leak",
                        is_deleted=False,
                    ),
                )
            )
            await session.commit()

        async with session_factory() as session:
            repository = ProfileCommentRepository(session=session)
            public_rows, public_total = await repository.get_comments_by_user(user.id)
            admin_rows, admin_total = await repository.get_comments_by_user(
                user.id,
                include_deleted=True,
            )

            assert public_total == 1
            assert [comment.contents for comment, _post in public_rows] == [
                "visible comment"
            ]
            assert admin_total == 2
            assert {comment.contents for comment, _post in admin_rows} == {
                "visible comment",
                "must not leak",
            }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_redis_otp_is_consumed_by_exactly_one_concurrent_request():
    redis = Redis.from_url(_redis_url(), decode_responses=True)
    service = OTPService(redis=redis)
    email = "concurrent@example.com"

    try:
        await redis.flushdb()
        await service.save_otp(email, 123456, purpose="reset")

        results = await asyncio.gather(
            *(
                service.verify_and_consume(email, 123456, purpose="reset")
                for _ in range(20)
            )
        )

        assert results.count(OTPVerifyResult.VERIFIED) == 1
        assert all(
            result in {OTPVerifyResult.VERIFIED, OTPVerifyResult.EXPIRED_OR_MISSING}
            for result in results
        )
    finally:
        await redis.flushdb()
        await redis.aclose()


@pytest.mark.asyncio
async def test_redis_otp_attempt_limit_and_reissue_reset():
    redis = Redis.from_url(_redis_url(), decode_responses=True)
    service = OTPService(redis=redis)
    email = "attempts@example.com"

    try:
        await redis.flushdb()
        await service.save_otp(email, 123456, purpose="signup")

        failures = [
            await service.verify_and_consume(email, 111111, purpose="signup")
            for _ in range(service.max_verify_attempts)
        ]
        assert failures[-1] is OTPVerifyResult.TOO_MANY_ATTEMPTS

        await service.save_otp(email, 654321, purpose="signup")
        assert (
            await service.verify_and_consume(email, 654321, purpose="signup")
            is OTPVerifyResult.VERIFIED
        )
    finally:
        await redis.flushdb()
        await redis.aclose()


@pytest.mark.asyncio
async def test_redis_login_attempts_are_capped_under_concurrency():
    redis = Redis.from_url(_redis_url(), decode_responses=True)
    service = LoginRateLimitService(redis=redis)
    email = "Brute@Example.com"
    ip = "203.0.113.7"

    try:
        await redis.flushdb()

        results = await asyncio.gather(
            *(service.acquire_attempt(email, ip) for _ in range(30))
        )

        assert results.count(True) == service.max_per_email
        email_key = service._email_key(email)
        ip_key = service._ip_key(ip)
        # 막힌 요청은 카운터를 올리지 않는다
        assert int(await redis.get(email_key)) == service.max_per_email
        assert int(await redis.get(ip_key)) == service.max_per_email
        assert 0 < await redis.ttl(email_key) <= service.window

        await service.reset(email, ip)
        assert await redis.get(email_key) is None
        assert int(await redis.get(ip_key)) == service.max_per_email - 1
    finally:
        await redis.flushdb()
        await redis.aclose()


@pytest.mark.asyncio
async def test_postgres_email_lookup_is_case_insensitive_via_normalization():
    engine = create_async_engine(_database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE likes, comments, uploads, posts, categories, users "
                    "RESTART IDENTITY CASCADE"
                )
            )

        signup = SignUpRequest(email="foo@x.com", password="password123", nickname="foo")
        async with session_factory() as session:
            await UserRepository(session=session).save_user(
                User.create(
                    email=signup.email,
                    hashed_password="$2b$12$integration",
                    nickname=signup.nickname,
                )
            )

        login = LogInRequest(email="Foo@X.com", password="password123")
        async with session_factory() as session:
            repository = UserRepository(session=session)
            found = await repository.get_user_by_email(login.email)
            assert found is not None and found.email == "foo@x.com"

            duplicate = SignUpRequest(email="FOO@x.com", password="password123", nickname="f2")
            assert await repository.get_user_by_email(duplicate.email) is not None
    finally:
        await engine.dispose()
