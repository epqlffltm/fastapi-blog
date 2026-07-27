#app/tests/test_user.py

'''
2026-07-23
회원 API 테스트

2026-07-24
httpOnly 쿠키 로그인 / 로그아웃
권한 반영
'''

import jwt
import pytest
from datetime import datetime, timedelta, timezone
from app.database.connection import settings
from app.database.orm import User
from app.service.auth import AuthService


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
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
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


def test_sign_up_duplicate_nickname(client, mock_user_repo):
    mock_user_repo.get_user_by_email.return_value = None
    mock_user_repo.get_user_by_nickname.return_value = _make_user()  # 닉네임 중복

    response = client.post(
        "/user/sign-up",
        json={"email": "new@example.com", "password": "password123", "nickname": "tester"},
    )

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

    assert service.decode_jwt(token) == 42


def test_decode_expired_token():
    service = AuthService()
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        service.decode_jwt(expired)


def test_decode_tampered_token():
    service = AuthService()
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(days=1)},
        "wrong-secret-key-that-is-long-enough-to-avoid-a-warning",   # 다른 키로 서명
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.InvalidSignatureError):
        service.decode_jwt(forged)
        
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


def test_send_password_change_otp(auth_client, mock_redis, mock_email_service):
    """코드 발송 요청 → 200"""
    mock_redis.set.return_value = True      # 쿨다운 통과
    response = auth_client.post("/user/me/password/otp")
    assert response.status_code == 200


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