#app/tests/test_otp.py

'''
2026-07-23
OTP API 테스트
'''

from unittest.mock import Mock
from redis import Redis
from app.service.otp import OTPService


# ---------- 발급 ----------

def test_create_otp(auth_client, mock_redis):
    response = auth_client.post("/user/email/otp")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert 100_000 <= data["otp"] <= 999_999
    # TTL과 함께 저장됐는지
    mock_redis.set.assert_called_once()
    assert mock_redis.set.call_args.kwargs["ex"] == 180


def test_create_otp_without_token(client, mock_redis):
    response = client.post("/user/email/otp")

    assert response.status_code == 401
    mock_redis.set.assert_not_called()


def test_create_otp_already_verified(auth_client, current_user, mock_redis):
    current_user.is_verified = True

    response = auth_client.post("/user/email/otp")

    assert response.status_code == 409
    mock_redis.set.assert_not_called()


# ---------- 검증 ----------

def test_verify_otp(auth_client, mock_redis, mock_user_repo, current_user):
    mock_redis.get.return_value = "123456"

    response = auth_client.post("/user/email/otp/verify", json={"otp": 123456})

    assert response.status_code == 200
    assert response.json()["is_verified"] is True
    assert current_user.is_verified is True
    mock_redis.delete.assert_called_once()      # 1회용이므로 폐기됐나
    mock_user_repo.update_user.assert_called_once()


def test_verify_otp_wrong(auth_client, mock_redis, mock_user_repo, current_user):
    mock_redis.get.return_value = "123456"

    response = auth_client.post("/user/email/otp/verify", json={"otp": 999999})

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid otp"
    assert current_user.is_verified is False
    mock_redis.delete.assert_not_called()


def test_verify_otp_expired(auth_client, mock_redis, mock_user_repo, current_user):
    mock_redis.get.return_value = None          # TTL 만료로 사라진 상태

    response = auth_client.post("/user/email/otp/verify", json={"otp": 123456})

    assert response.status_code == 400
    assert response.json()["detail"] == "otp expired or not issued"
    assert current_user.is_verified is False


def test_verify_otp_invalid_format(auth_client, mock_redis, mock_user_repo):
    response = auth_client.post("/user/email/otp/verify", json={"otp": 123})

    assert response.status_code == 422       # 6자리가 아니면 스키마에서 걸림


# ---------- 서비스 자체 ----------

def test_otp_is_six_digits():
    for _ in range(100):
        otp = OTPService.create_otp()
        assert 100_000 <= otp <= 999_999


def test_otp_key_separated_by_purpose():
    """용도별로 키가 분리돼야 가입 코드로 비번을 못 바꾼다"""
    service = OTPService(redis=Mock(spec=Redis))
    key = service._key("test@example.com")

    assert key == "otp:signup:test@example.com"