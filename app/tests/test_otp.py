#app/tests/test_otp.py

'''
2026-07-23
OTP API 테스트

2026-07-24
이메일 발송 / 재발급 제한 반영
'''

from unittest.mock import Mock
from redis import Redis
from app.service.otp import OTPService


# ---------- 발급 ----------

def test_create_otp(auth_client, current_user, mock_redis, mock_email_service):
    current_user.is_verified = False

    response = auth_client.post("/user/email/otp")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "otp" not in data                 # 코드가 응답에 새면 안 된다
    mock_email_service.send_otp.assert_called_once()
    otp_sent = mock_email_service.send_otp.call_args.args[1]
    assert 100_000 <= otp_sent <= 999_999


def test_create_otp_cooldown(auth_client, current_user, mock_redis, mock_email_service):
    current_user.is_verified = False
    mock_redis.set.side_effect = [None]       # 제한 키가 이미 있는 상태

    response = auth_client.post("/user/email/otp")

    assert response.status_code == 429
    mock_email_service.send_otp.assert_not_called()


def test_create_otp_without_token(client, mock_redis, mock_email_service):
    response = client.post("/user/email/otp")

    assert response.status_code == 401
    mock_email_service.send_otp.assert_not_called()


def test_create_otp_already_verified(auth_client, mock_redis, mock_email_service):
    response = auth_client.post("/user/email/otp")      # current_user는 인증됨

    assert response.status_code == 409
    mock_email_service.send_otp.assert_not_called()


# ---------- 검증 ----------

def test_verify_otp(auth_client, current_user, mock_redis, mock_user_repo):
    current_user.is_verified = False
    mock_redis.get.return_value = "123456"

    response = auth_client.post("/user/email/otp/verify", json={"otp": 123456})

    assert response.status_code == 200
    assert response.json()["is_verified"] is True
    assert current_user.is_verified is True
    mock_redis.delete.assert_called_once()      # 1회용이므로 폐기됐나
    mock_user_repo.update_user.assert_called_once()


def test_verify_otp_wrong(auth_client, current_user, mock_redis, mock_user_repo):
    current_user.is_verified = False
    mock_redis.get.return_value = "123456"

    response = auth_client.post("/user/email/otp/verify", json={"otp": 999999})

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid otp"
    assert current_user.is_verified is False
    mock_redis.delete.assert_not_called()


def test_verify_otp_expired(auth_client, current_user, mock_redis, mock_user_repo):
    current_user.is_verified = False
    mock_redis.get.return_value = None          # TTL 만료로 사라진 상태

    response = auth_client.post("/user/email/otp/verify", json={"otp": 123456})

    assert response.status_code == 400
    assert response.json()["detail"] == "otp expired or not issued"
    assert current_user.is_verified is False


def test_verify_otp_invalid_format(auth_client, mock_redis, mock_user_repo):
    response = auth_client.post("/user/email/otp/verify", json={"otp": 123})

    assert response.status_code == 422       # 6자리가 아니면 스키마에서 걸림


# ---------- 미인증 계정 제한 ----------

def test_unverified_cannot_create_post(unverified_client, mock_post_repo):
    response = unverified_client.post("/page", json={"title": "글", "contents": "본문"})

    assert response.status_code == 403
    assert response.json()["detail"] == "email not verified"
    mock_post_repo.save_with_images.assert_not_called()


def test_unverified_cannot_create_comment(unverified_client, mock_post_repo, mock_comment_repo):
    response = unverified_client.post("/page/1/comment", json={"contents": "댓글"})

    assert response.status_code == 403
    mock_comment_repo.save.assert_not_called()


def test_unverified_can_read(unverified_client, mock_post_repo):
    """읽기는 인증 없이도 가능"""
    mock_post_repo.get_posts.return_value = []

    response = unverified_client.get("/pages")

    assert response.status_code == 200


# ---------- 서비스 자체 ----------

def test_otp_is_six_digits():
    for _ in range(100):
        otp = OTPService.create_otp()
        assert 100_000 <= otp <= 999_999


def test_otp_key_separated_by_purpose():
    """용도별로 키가 분리돼야 가입 코드로 비번을 못 바꾼다"""
    service = OTPService(redis=Mock(spec=Redis))

    assert service._key("test@example.com") == "otp:signup:test@example.com"
    assert service._cooldown_key("test@example.com") == "otp:cooldown:signup:test@example.com"