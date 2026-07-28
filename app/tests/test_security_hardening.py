"""인증·설정·Redis 장애 격리 회귀 테스트."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.database.connection import Settings
from app.database.orm import Category, Post, User
from app.schema.request import (
    PasswordChangeRequest,
    ResetPasswordVerifyRequest,
    SignUpRequest,
)
from app.service.auth import AuthService
from app.service.password import BCRYPT_MAX_PASSWORD_BYTES


def _make_user() -> User:
    return User(
        id=1,
        email="test@example.com",
        password="$2b$12$fakehashedpassword",
        nickname="tester",
        is_verified=True,
        can_comment=True,
        can_write_post=True,
        can_upload=True,
        can_manage_category=True,
        can_manage_user=True,
        can_manage_post=True,
        suspended_until=None,
        is_banned=False,
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )


def _make_post() -> Post:
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    post = Post(
        id=1,
        title="테스트 글",
        contents="본문",
        user_id=1,
        category_id=1,
        thumbnail_url=None,
        created_at=now,
        updated_at=now,
        is_deleted=False,
        view_count=5,
    )
    post.user = _make_user()
    post.category = Category(id=1, slug="dev", name="개발", display_order=0)
    post.comments = []
    return post


def _settings(**overrides) -> Settings:
    values = {
        "database_url": "postgresql+asyncpg://user:password@localhost:5432/blog",
        "jwt_secret_key": "a" * 32,
        "jwt_algorithm": "HS256",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            SignUpRequest,
            {
                "email": "test@example.com",
                "password": "가" * 25,
                "nickname": "tester",
            },
        ),
        (
            ResetPasswordVerifyRequest,
            {
                "email": "test@example.com",
                "otp": 123456,
                "new_password": "가" * 25,
            },
        ),
        (
            PasswordChangeRequest,
            {
                "current_password": "oldpass123",
                "new_password": "가" * 25,
                "otp": 123456,
            },
        ),
    ],
)
def test_new_password_rejects_more_than_72_utf8_bytes(model, payload):
    """25자 한글은 75바이트이므로 문자 수가 72 미만이어도 거부해야 한다."""
    with pytest.raises(ValidationError, match="72 UTF-8 bytes"):
        model(**payload)


def test_new_password_accepts_exactly_72_utf8_bytes():
    password = "a" * BCRYPT_MAX_PASSWORD_BYTES

    request = SignUpRequest(
        email="test@example.com",
        password=password,
        nickname="tester",
    )

    assert request.password == password


def test_hash_password_rejects_overlong_input_before_bcrypt(monkeypatch):
    hashpw = Mock()
    monkeypatch.setattr("app.service.auth.bcrypt.hashpw", hashpw)

    with pytest.raises(ValueError, match="72 UTF-8 bytes"):
        AuthService().hash_password("가" * 25)

    hashpw.assert_not_called()


def test_verify_password_treats_overlong_input_as_mismatch(monkeypatch):
    checkpw = Mock()
    monkeypatch.setattr("app.service.auth.bcrypt.checkpw", checkpw)

    matched = AuthService().verify_password(
        "가" * 25,
        "$2b$12$fakehashedpassword",
    )

    assert matched is False
    checkpw.assert_not_called()


@pytest.mark.asyncio
async def test_hash_password_async_runs_in_threadpool(monkeypatch):
    calls = {}

    async def fake_run_in_threadpool(function, *args):
        calls["function"] = function
        calls["args"] = args
        return "hashed"

    monkeypatch.setattr(
        "app.service.auth.run_in_threadpool",
        fake_run_in_threadpool,
    )

    service = AuthService()
    result = await service.hash_password_async("password123")

    assert result == "hashed"
    assert calls["function"].__self__ is service
    assert calls["function"].__func__ is AuthService.hash_password
    assert calls["args"] == ("password123",)


@pytest.mark.asyncio
async def test_verify_password_async_runs_in_threadpool(monkeypatch):
    calls = {}

    async def fake_run_in_threadpool(function, *args):
        calls["function"] = function
        calls["args"] = args
        return True

    monkeypatch.setattr(
        "app.service.auth.run_in_threadpool",
        fake_run_in_threadpool,
    )

    service = AuthService()
    result = await service.verify_password_async("password123", "hash")

    assert result is True
    assert calls["function"].__self__ is service
    assert calls["function"].__func__ is AuthService.verify_password
    assert calls["args"] == ("password123", "hash")


def test_login_overlong_password_returns_generic_401(
    client,
    mock_user_repo,
    mock_rate_limit,
):
    user = _make_user()
    user.password = AuthService().hash_password("password123")
    mock_user_repo.get_user_by_email.return_value = user

    response = client.post(
        "/user/log-in",
        json={
            "email": "test@example.com",
            "password": "가" * 25,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid email or password"
    mock_rate_limit.record_failure.assert_awaited_once()


def test_sign_up_overlong_password_returns_422(client, mock_user_repo):
    response = client.post(
        "/user/sign-up",
        json={
            "email": "test@example.com",
            "password": "가" * 25,
            "nickname": "tester",
        },
    )

    assert response.status_code == 422
    mock_user_repo.get_user_by_email.assert_not_called()
    mock_user_repo.save_user.assert_not_called()


def test_short_jwt_secret_is_rejected():
    with pytest.raises(ValidationError, match="at least 32 UTF-8 bytes"):
        _settings(jwt_secret_key="too-short")


def test_jwt_algorithm_is_restricted_to_hs256():
    with pytest.raises(ValidationError):
        _settings(jwt_algorithm="none")


def test_redis_failure_does_not_block_post_read(
    client,
    mock_post_repo,
    mock_redis,
):
    post = _make_post()
    mock_post_repo.get_post_by_id.return_value = post
    mock_redis.set.side_effect = ConnectionError("redis down")

    response = client.get("/page/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["view_count"] == 5
    mock_post_repo.increment_view_count.assert_not_called()
