#app/tests/test_user.py

'''
2026-07-23
회원 API 테스트

2026-07-24
httpOnly 쿠키 로그인 / 로그아웃
권한 반영

2026-09-30
로그인 시도 원자 제한 (순차·동시 요청) 테스트
이메일 대소문자 정규화 (가입 중복·로그인) 테스트
'''

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy.exc import IntegrityError

from app.database.connection import settings
from app.database.orm import User
from app.service.auth import AuthService
from app.service.otp import OTPService
from app.service.ratelimit import LoginRateLimitService


def _make_user(id=1, email="test@example.com", nickname="tester"):
    return User(
        id=id,
        email=email,
        password="$2b$12$fakehashedpassword",
        nickname=nickname,
        is_verified=False,
        can_comment=True,
        can_write_post=False,
        can_upload=False,
        can_manage_category=False,
        can_manage_user=False,
        suspended_until=None,
        is_banned=False,
        created_at=datetime(2026, 7, 23, tzinfo=UTC),
        can_manage_post=False,
    )


# ---------- 회원가입 ----------

def test_sign_up(client, mock_user_repo):
    mock_user_repo.get_user_by_email.return_value = None      # 중복 없음
    mock_user_repo.get_user_by_nickname.return_value = None
    mock_user_repo.save_user.return_value = _make_user()

    response = client.post(
        "/user/sign-up",
        json={"email": "test@example.com", "password": "password123", "nickname": "tester"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["nickname"] == "tester"
    assert data["is_verified"] is False
    assert data["can_comment"] is True
    assert data["can_write_post"] is False
    assert "password" not in data          # 비번이 응답에 새면 안 된다
    mock_user_repo.save_user.assert_called_once()


def test_sign_up_duplicate_email(client, mock_user_repo):
    mock_user_repo.get_user_by_email.return_value = _make_user()   # 이미 존재

    response = client.post(
        "/user/sign-up",
        json={"email": "test@example.com", "password": "password123", "nickname": "other"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "email already exists"
    mock_user_repo.save_user.assert_not_called()


def test_sign_up_normalizes_email_case(client, mock_user_repo):
    """대소문자만 다른 이메일은 같은 계정이다. 저장·중복 검사 모두 소문자로."""
    mock_user_repo.get_user_by_email.return_value = None
    mock_user_repo.get_user_by_nickname.return_value = None
    mock_user_repo.save_user.return_value = _make_user(email="foo@x.com", nickname="foofoo")

    response = client.post(
        "/user/sign-up",
        json={"email": "  Foo@X.com ", "password": "password123", "nickname": "foofoo"},
    )

    assert response.status_code == 201
    mock_user_repo.get_user_by_email.assert_awaited_once_with("foo@x.com")
    saved = mock_user_repo.save_user.await_args.args[0]
    assert saved.email == "foo@x.com"


def test_sign_up_duplicate_email_different_case_rejected(client, mock_user_repo):
    mock_user_repo.get_user_by_email.side_effect = (
        lambda email: _make_user(email="foo@x.com") if email == "foo@x.com" else None
    )

    response = client.post(
        "/user/sign-up",
        json={"email": "FOO@x.com", "password": "password123", "nickname": "another"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "email already exists"
    mock_user_repo.save_user.assert_not_called()


def test_log_in_with_different_email_case(client, mock_user_repo, mock_rate_limit):
    """foo@x.com 으로 가입한 계정에 Foo@x.com 으로 로그인할 수 있다."""
    user = _make_user(email="foo@x.com")
    user.password = AuthService().hash_password("password123")
    mock_user_repo.get_user_by_email.side_effect = (
        lambda email: user if email == "foo@x.com" else None
    )

    response = client.post(
        "/user/log-in",
        json={"email": "Foo@x.com", "password": "password123"},
    )

    assert response.status_code == 200
    # 레이트리밋도 같은 표준형 이메일로 센다
    mock_rate_limit.acquire_attempt.assert_awaited_once_with("foo@x.com", "testclient")


def test_sign_up_duplicate_nickname(client, mock_user_repo):
    mock_user_repo.get_user_by_email.return_value = None
    mock_user_repo.get_user_by_nickname.return_value = _make_user()  # 닉네임 중복

    response = client.post(
        "/user/sign-up",
        json={"email": "new@example.com", "password": "password123", "nickname": "tester"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "nickname already exists"


def test_sign_up_integrity_conflict(client, mock_user_repo):
    """사전 조회 뒤 다른 요청이 먼저 가입해도 500 대신 409."""
    mock_user_repo.get_user_by_email.return_value = None
    mock_user_repo.get_user_by_nickname.return_value = None
    mock_user_repo.save_user.side_effect = IntegrityError(
        "duplicate user",
        {},
        Exception("unique violation"),
    )

    response = client.post(
        "/user/sign-up",
        json={
            "email": "test@example.com",
            "password": "password123",
            "nickname": "tester",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "email or nickname already exists"


def test_update_me_nickname_integrity_conflict(
    auth_client, current_user, mock_user_repo
):
    """닉네임 중복 경쟁 상태도 409로 처리한다."""
    mock_user_repo.get_user_by_nickname.return_value = None
    mock_user_repo.update_user.side_effect = IntegrityError(
        "duplicate nickname",
        {},
        Exception("unique violation"),
    )

    response = auth_client.patch("/user/me", json={"nickname": "taken"})

    assert response.status_code == 409
    assert response.json()["detail"] == "nickname already exists"


def test_sign_up_invalid_email(client, mock_user_repo):
    response = client.post(
        "/user/sign-up",
        json={"email": "not-an-email", "password": "password123", "nickname": "tester"},
    )

    assert response.status_code == 422


def test_sign_up_short_password(client, mock_user_repo):
    response = client.post(
        "/user/sign-up",
        json={"email": "test@example.com", "password": "short", "nickname": "tester"},
    )

    assert response.status_code == 422


# ---------- 해싱 자체 테스트 ----------

def test_hash_password():
    service = AuthService()
    hashed = service.hash_password("password123")

    assert hashed != "password123"          # 평문이 아니어야 한다
    assert hashed.startswith("$2b$")        # bcrypt 형식


def test_verify_password():
    service = AuthService()
    hashed = service.hash_password("password123")

    assert service.verify_password("password123", hashed) is True
    assert service.verify_password("wrongpassword", hashed) is False


def test_hash_is_salted():
    """같은 비번이어도 해시가 매번 달라야 한다 (salt)"""
    service = AuthService()
    h1 = service.hash_password("password123")
    h2 = service.hash_password("password123")

    assert h1 != h2
    assert service.verify_password("password123", h1) is True
    assert service.verify_password("password123", h2) is True


# ---------- 로그인 ----------

def test_log_in(client, mock_user_repo):
    service = AuthService()
    user = _make_user()
    user.password = service.hash_password("password123")   # 실제 해시로 교체
    mock_user_repo.get_user_by_email.return_value = user

    response = client.post(
        "/user/log-in",
        json={"email": "test@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["nickname"] == "tester"
    assert response.json()["can_comment"] is True
    assert "password" not in response.json()
    assert "access_token" not in response.text      # 토큰이 본문에 새면 안 된다

    set_cookie = response.headers["set-cookie"].lower()
    assert "access_token=" in set_cookie
    assert "httponly" in set_cookie                 # JS가 못 읽어야 한다
    assert "samesite=strict" in set_cookie          # CSRF 방어


def test_log_in_wrong_password(client, mock_user_repo):
    service = AuthService()
    user = _make_user()
    user.password = service.hash_password("password123")
    mock_user_repo.get_user_by_email.return_value = user

    response = client.post(
        "/user/log-in",
        json={"email": "test@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid email or password"
    assert "set-cookie" not in response.headers     # 실패 시 쿠키를 주면 안 된다


def test_log_in_no_such_email(client, mock_user_repo):
    mock_user_repo.get_user_by_email.return_value = None

    response = client.post(
        "/user/log-in",
        json={"email": "nobody@example.com", "password": "password123"},
    )

    assert response.status_code == 401
    # 없는 계정도 비번 틀림과 같은 메시지여야 한다
    assert response.json()["detail"] == "invalid email or password"


# ---------- 로그인 실패 횟수 제한 (브루트포스) ----------

def test_log_in_blocked_when_rate_limited(client, mock_user_repo, mock_rate_limit):
    """한도를 넘으면 429. 비밀번호 검증까지 가지 않아야 한다."""
    mock_rate_limit.acquire_attempt.return_value = False

    response = client.post(
        "/user/log-in",
        json={"email": "test@example.com", "password": "password123"},
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "too many login attempts"
    assert "set-cookie" not in response.headers
    # bcrypt 를 태우지 않으려면 조회조차 하면 안 된다
    mock_user_repo.get_user_by_email.assert_not_called()


def test_log_in_wrong_password_counts_attempt(client, mock_user_repo, mock_rate_limit):
    user = _make_user()
    user.password = AuthService().hash_password("password123")
    mock_user_repo.get_user_by_email.return_value = user

    response = client.post(
        "/user/log-in",
        json={"email": "test@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401
    # 시도는 검증 전에 이미 세었다. 실패했으니 되돌리지 않는다
    mock_rate_limit.acquire_attempt.assert_awaited_once()
    mock_rate_limit.reset.assert_not_awaited()


def test_log_in_unknown_email_also_counts_attempt(
    client, mock_user_repo, mock_rate_limit
):
    """없는 계정도 똑같이 센다. 안 그러면 응답 차이로 가입 여부가 샌다."""
    mock_user_repo.get_user_by_email.return_value = None

    response = client.post(
        "/user/log-in",
        json={"email": "nobody@example.com", "password": "password123"},
    )

    assert response.status_code == 401
    mock_rate_limit.acquire_attempt.assert_awaited_once()
    mock_rate_limit.reset.assert_not_awaited()


def test_log_in_success_resets_counter(client, mock_user_repo, mock_rate_limit):
    user = _make_user()
    user.password = AuthService().hash_password("password123")
    mock_user_repo.get_user_by_email.return_value = user

    response = client.post(
        "/user/log-in",
        json={"email": "test@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    mock_rate_limit.reset.assert_awaited_once_with("test@example.com", "testclient")


def _wrong_password_user() -> User:
    user = _make_user()
    user.password = AuthService().hash_password("password123")
    return user


def test_log_in_sequential_limit_unchanged(client, mock_user_repo, mock_redis):
    """순차 요청: 5번까지는 401, 6번째부터 429 (기존 동작 그대로)."""
    mock_user_repo.get_user_by_email.return_value = _wrong_password_user()

    codes = [
        client.post(
            "/user/log-in",
            json={"email": "test@example.com", "password": "wrongpassword"},
        ).status_code
        for _ in range(LoginRateLimitService.max_per_email + 2)
    ]

    assert codes == [401] * LoginRateLimitService.max_per_email + [429, 429]


def test_log_in_success_clears_email_counter_keeps_ip_failures(
    client, mock_user_repo, mock_redis
):
    user = _wrong_password_user()
    mock_user_repo.get_user_by_email.return_value = user

    for _ in range(3):
        client.post(
            "/user/log-in",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )
    response = client.post(
        "/user/log-in",
        json={"email": "test@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert "login-fail:email:test@example.com" not in mock_redis.counters
    # 성공한 시도 몫(1)만 빠지고 실패 3번은 남는다
    assert mock_redis.counters["login-fail:ip:testclient"] == 3


@pytest.mark.asyncio
async def test_log_in_concurrent_requests_cannot_exceed_limit(
    mock_user_repo, mock_redis, monkeypatch
):
    """동시에 몰린 틀린 로그인 중 한도만큼만 비밀번호 검증까지 간다.

    예전 코드는 검증(느림)이 끝난 뒤에야 실패를 기록해서, 동시에 들어온
    요청이 모두 같은 카운트를 보고 통과했다.
    """
    import asyncio

    import httpx

    from app.main import app

    mock_user_repo.get_user_by_email.return_value = _wrong_password_user()
    checked = 0

    async def slow_wrong_verify(self, password, hashed):
        nonlocal checked
        checked += 1
        await asyncio.sleep(0.05)   # bcrypt 처럼 느린 구간에서 다른 요청이 끼어든다
        return False

    monkeypatch.setattr(AuthService, "verify_password_async", slow_wrong_verify)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        responses = await asyncio.gather(
            *(
                ac.post(
                    "/user/log-in",
                    json={"email": "test@example.com", "password": "wrongpassword"},
                )
                for _ in range(20)
            )
        )

    codes = [r.status_code for r in responses]
    limit = LoginRateLimitService.max_per_email
    assert checked == limit
    assert codes.count(401) == limit
    assert codes.count(429) == 20 - limit


@pytest.mark.asyncio
async def test_rate_limit_allows_under_threshold(mock_redis):
    service = LoginRateLimitService(redis=mock_redis)
    mock_redis.eval.return_value = 1

    assert await service.acquire_attempt("test@example.com", "1.2.3.4") is True


@pytest.mark.asyncio
async def test_rate_limit_blocks_over_threshold(mock_redis):
    service = LoginRateLimitService(redis=mock_redis)
    mock_redis.eval.return_value = 0

    assert await service.acquire_attempt("test@example.com", "1.2.3.4") is False


@pytest.mark.asyncio
async def test_rate_limit_fails_open_when_redis_down(mock_redis):
    """Redis 장애로 전 사용자 로그인이 막히는 쪽이 더 큰 사고다."""
    mock_redis.eval.side_effect = ConnectionError("redis down")

    service = LoginRateLimitService(redis=mock_redis)
    assert await service.acquire_attempt("test@example.com", "1.2.3.4") is True


@pytest.mark.asyncio
async def test_rate_limit_reset_clears_email_counter_only(mock_redis):
    """IP 카운터는 이번 성공 몫만 뺀다 — 자기 계정 로그인으로 IP 한도를 초기화하지 못하게."""
    service = LoginRateLimitService(redis=mock_redis)
    mock_redis.counters["login-fail:email:test@example.com"] = 4
    mock_redis.counters["login-fail:ip:1.2.3.4"] = 10

    await service.reset("Test@Example.com", "1.2.3.4")

    assert "login-fail:email:test@example.com" not in mock_redis.counters
    assert mock_redis.counters["login-fail:ip:1.2.3.4"] == 9


def test_banned_can_still_log_in(client, mock_user_repo):
    """본인이 제재 상태를 확인할 수 있어야 하므로 로그인은 막지 않는다"""
    service = AuthService()
    user = _make_user()
    user.password = service.hash_password("password123")
    user.is_banned = True
    mock_user_repo.get_user_by_email.return_value = user

    response = client.post(
        "/user/log-in",
        json={"email": "test@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["is_banned"] is True


# ---------- 로그아웃 ----------

def test_log_out(client):
    response = client.post("/user/log-out")

    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"].lower()
    assert "access_token=" in set_cookie
    assert 'max-age=0' in set_cookie or 'expires=' in set_cookie   # 삭제 지시


# ---------- 내 정보 (쿠키 인증) ----------

def test_get_me(client, mock_user_repo):
    user = _make_user()
    mock_user_repo.get_user_by_id.return_value = user
    client.cookies.set("access_token", AuthService().create_jwt(user.id))

    response = client.get("/user/me")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["is_suspended"] is False
    assert "password" not in data


def test_get_me_without_cookie(client, mock_user_repo):
    response = client.get("/user/me")

    assert response.status_code == 401


def test_get_me_invalid_cookie(client, mock_user_repo):
    client.cookies.set("access_token", "garbage")

    response = client.get("/user/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid token"


# ---------- JWT 자체 테스트 ----------

def test_jwt_roundtrip():
    service = AuthService()
    token = service.create_jwt(user_id=42)

    assert service.decode_jwt_claims(token).user_id == 42


def test_decode_expired_token():
    service = AuthService()
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) - timedelta(seconds=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        service.decode_jwt_claims(expired)


def test_decode_tampered_token():
    service = AuthService()
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) + timedelta(days=1)},
        "wrong-secret-key-that-is-long-enough-to-avoid-a-warning",   # 다른 키로 서명
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.InvalidSignatureError):
        service.decode_jwt_claims(forged)
        
def test_change_password(auth_client, mock_user_repo, current_user, mock_redis):
    """현재 비번 + 올바른 OTP → 변경"""
    service = AuthService()
    current_user.password = service.hash_password("oldpass123")
    mock_redis.get.return_value = "123456"      # 저장된 OTP (문자열로 반환됨)

    response = auth_client.patch("/user/me/password", json={
        "current_password": "oldpass123",
        "new_password": "newpass456",
        "otp": 123456,
    })

    assert response.status_code == 200
    assert service.verify_password("newpass456", current_user.password) is True
    mock_user_repo.update_user.assert_called_once()
    mock_redis.delete.assert_awaited_once()


def test_change_password_wrong_otp(auth_client, mock_user_repo, current_user, mock_redis):
    """OTP 틀리면 400, 안 바뀐다"""
    service = AuthService()
    current_user.password = service.hash_password("oldpass123")
    mock_redis.get.return_value = "123456"

    response = auth_client.patch("/user/me/password", json={
        "current_password": "oldpass123",
        "new_password": "newpass456",
        "otp": 999999,
    })

    assert response.status_code == 400
    mock_user_repo.update_user.assert_not_called()


def test_change_password_no_otp_issued(auth_client, mock_user_repo, current_user, mock_redis):
    """코드를 안 받았으면(만료/미발급) 400"""
    service = AuthService()
    current_user.password = service.hash_password("oldpass123")
    mock_redis.get.return_value = None      # 저장된 OTP 없음

    response = auth_client.patch("/user/me/password", json={
        "current_password": "oldpass123",
        "new_password": "newpass456",
        "otp": 123456,
    })

    assert response.status_code == 400
    mock_user_repo.update_user.assert_not_called()


def test_change_password_wrong_current(auth_client, mock_user_repo, current_user, mock_redis):
    """현재 비번 틀리면 403 (OTP 검사 전에 막힘)"""
    service = AuthService()
    current_user.password = service.hash_password("oldpass123")
    mock_redis.get.return_value = "123456"

    response = auth_client.patch("/user/me/password", json={
        "current_password": "WRONGpass",
        "new_password": "newpass456",
        "otp": 123456,
    })

    assert response.status_code == 403
    mock_user_repo.update_user.assert_not_called()


def test_change_password_requires_login(client, mock_user_repo):
    response = client.patch("/user/me/password", json={
        "current_password": "x", "new_password": "newpass456", "otp": 123456,
    })
    assert response.status_code == 401
    mock_user_repo.update_user.assert_not_called()


def test_create_otp_uses_secrets(monkeypatch):
    """OTP 생성은 random이 아니라 secrets를 사용한다."""
    monkeypatch.setattr("app.service.otp.secrets.randbelow", lambda upper: 0)
    assert OTPService.create_otp() == 100_000


@pytest.mark.asyncio
async def test_otp_send_slot_allowed(mock_redis):
    service = OTPService(redis=mock_redis)
    mock_redis.eval.return_value = 1

    assert await service.acquire_send_slot("test@example.com", purpose="signup") is True
    mock_redis.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_otp_send_slot_rejected(mock_redis):
    service = OTPService(redis=mock_redis)
    mock_redis.eval.return_value = 0

    assert await service.acquire_send_slot("test@example.com", purpose="signup") is False


def test_send_password_change_otp(auth_client, mock_redis, mock_email_service):
    """코드 발송 제한 통과 → 200"""
    mock_redis.eval.return_value = 1
    response = auth_client.post("/user/me/password/otp")

    assert response.status_code == 200
    mock_email_service.send_password_reset.assert_called_once()


def test_send_password_change_otp_rate_limited(
    auth_client, mock_redis, mock_email_service
):
    """1분 쿨다운 또는 시간당 제한에 걸리면 429."""
    mock_redis.eval.return_value = 0
    response = auth_client.post("/user/me/password/otp")

    assert response.status_code == 429
    assert response.json()["detail"] == "too many requests"
    mock_email_service.send_password_reset.assert_not_called()


def test_signup_otp_rate_limited(
    unverified_client, mock_redis, mock_email_service
):
    mock_redis.eval.return_value = 0
    response = unverified_client.post("/user/email/otp")

    assert response.status_code == 429
    assert response.json()["detail"] == "too many requests"
    mock_email_service.send_otp.assert_not_called()


def test_password_reset_rate_limit_keeps_generic_response(
    client, mock_user_repo, mock_redis, mock_email_service
):
    """재설정 요청은 제한에 걸려도 계정 존재 여부를 숨기기 위해 같은 200 응답."""
    mock_user_repo.get_user_by_email.return_value = _make_user()
    mock_redis.eval.return_value = 0

    response = client.post(
        "/user/password/reset",
        json={"email": "test@example.com"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "if the email exists, a code has been sent"
    }
    mock_email_service.send_password_reset.assert_not_called()


def test_change_password_short(auth_client, mock_user_repo, current_user, mock_redis):
    """새 비번이 8자 미만이면 422 (검증에서 막힘)"""
    service = AuthService()
    current_user.password = service.hash_password("oldpass123")
    mock_redis.get.return_value = "123456"

    response = auth_client.patch("/user/me/password", json={
        "current_password": "oldpass123",
        "new_password": "short",
        "otp": 123456,
    })

    assert response.status_code == 422
    mock_user_repo.update_user.assert_not_called()
    
def test_get_public_profile(client, mock_user_repo):
    """남의 공개 프로필 — 공개 정보만 나오고 이메일·권한은 안 나온다"""
    user = _make_user(id=3, nickname="other")
    user.bio = "안녕"
    user.email = "secret@example.com"
    mock_user_repo.get_user_by_id.return_value = user

    response = client.get("/user/3/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["nickname"] == "other"
    assert body["bio"] == "안녕"
    # 공개 프로필엔 이메일·권한이 절대 없어야 한다
    assert "email" not in body
    assert "can_manage_user" not in body


def test_get_public_profile_not_found(client, mock_user_repo):
    mock_user_repo.get_user_by_id.return_value = None
    response = client.get("/user/999/profile")
    assert response.status_code == 404