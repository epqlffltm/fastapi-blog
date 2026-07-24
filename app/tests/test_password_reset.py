#app/tests/test_password_reset.py

'''
2026-07-24
비밀번호 재설정 API 테스트
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
        is_verified=True,
        created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )


# ---------- 코드 발송 ----------

def test_reset_password_sends_code(client, mock_user_repo, mock_redis, mock_email_service):
    mock_user_repo.get_user_by_email.return_value = _make_user()

    response = client.post("/user/password/reset", json={"email": "test@example.com"})

    assert response.status_code == 200
    mock_email_service.send_password_reset.assert_called_once()
    otp_sent = mock_email_service.send_password_reset.call_args.args[1]
    assert 100_000 <= otp_sent <= 999_999


def test_reset_password_unknown_email(client, mock_user_repo, mock_redis, mock_email_service):
    """없는 계정이어도 같은 응답 (가입 여부가 새면 안 된다)"""
    mock_user_repo.get_user_by_email.return_value = None

    response = client.post("/user/password/reset", json={"email": "nobody@example.com"})

    assert response.status_code == 200
    mock_email_service.send_password_reset.assert_not_called()


def test_reset_password_same_message_either_way(
    client, mock_user_repo, mock_redis, mock_email_service
):
    """존재하는 계정과 없는 계정의 응답이 완전히 같아야 한다"""
    mock_user_repo.get_user_by_email.return_value = _make_user()
    existing = client.post("/user/password/reset", json={"email": "test@example.com"})

    mock_user_repo.get_user_by_email.return_value = None
    missing = client.post("/user/password/reset", json={"email": "nobody@example.com"})

    assert existing.status_code == missing.status_code
    assert existing.json() == missing.json()


def test_reset_password_cooldown(client, mock_user_repo, mock_redis, mock_email_service):
    mock_user_repo.get_user_by_email.return_value = _make_user()
    mock_redis.set.return_value = None        # 제한 키가 이미 있음

    response = client.post("/user/password/reset", json={"email": "test@example.com"})

    assert response.status_code == 200        # 여기서도 티를 내지 않는다
    mock_email_service.send_password_reset.assert_not_called()


# ---------- 재설정 실행 ----------

def test_reset_password_verify(client, mock_user_repo, mock_redis):
    user = _make_user()
    old_hash = user.password
    mock_redis.get.return_value = "123456"
    mock_user_repo.get_user_by_email.return_value = user

    response = client.post(
        "/user/password/reset/verify",
        json={"email": "test@example.com", "otp": 123456, "new_password": "newpassword123"},
    )

    assert response.status_code == 200
    assert user.password != old_hash                    # 실제로 바뀌었나
    assert AuthService().verify_password("newpassword123", user.password)
    mock_redis.delete.assert_called_once()              # 1회용이므로 폐기
    mock_user_repo.update_user.assert_called_once()


def test_reset_password_verify_wrong_otp(client, mock_user_repo, mock_redis):
    user = _make_user()
    old_hash = user.password
    mock_redis.get.return_value = "123456"
    mock_user_repo.get_user_by_email.return_value = user

    response = client.post(
        "/user/password/reset/verify",
        json={"email": "test@example.com", "otp": 999999, "new_password": "newpassword123"},
    )

    assert response.status_code == 400
    assert user.password == old_hash
    mock_user_repo.update_user.assert_not_called()


def test_reset_password_verify_expired(client, mock_user_repo, mock_redis):
    mock_redis.get.return_value = None       # TTL 만료

    response = client.post(
        "/user/password/reset/verify",
        json={"email": "test@example.com", "otp": 123456, "new_password": "newpassword123"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "otp expired or not issued"
    mock_user_repo.update_user.assert_not_called()


def test_reset_password_verify_short_password(client, mock_user_repo, mock_redis):
    response = client.post(
        "/user/password/reset/verify",
        json={"email": "test@example.com", "otp": 123456, "new_password": "short"},
    )

    assert response.status_code == 422       # 가입과 같은 길이 정책