#app/tests/test_user.py

'''
2026-07-23
회원 API 테스트

2026-07-24
쿠키 방식으로 변경
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
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
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
    assert "password" not in data


def test_get_me_without_cookie(client, mock_user_repo):
    response = client.get("/user/me")

    assert response.status_code == 401


def test_get_me_invalid_cookie(client, mock_user_repo):
    client.cookies.set("access_token", "garbage")

    response = client.get("/user/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid token"
    
'''
# ---------- 내 정보 (토큰 인증) ----------

def test_get_me(client, mock_user_repo):
    user = _make_user()
    mock_user_repo.get_user_by_id.return_value = user
    token = AuthService().create_jwt(user.id)

    response = client.get("/user/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "password" not in data


def test_get_me_without_token(client, mock_user_repo):
    response = client.get("/user/me")

    assert response.status_code == 401


def test_get_me_invalid_token(client, mock_user_repo):
    response = client.get("/user/me", headers={"Authorization": "Bearer garbage"})

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid token"

'''
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
        "wrong-secret-key",      # 다른 키로 서명
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.InvalidSignatureError):
        service.decode_jwt(forged)
