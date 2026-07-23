#app/tests/test_user.py

'''
2026-07-23
회원 API 테스트
'''

from datetime import datetime, timezone
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