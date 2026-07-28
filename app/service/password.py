"""비밀번호 입력 정책과 bcrypt 바이트 길이 검증."""

BCRYPT_MAX_PASSWORD_BYTES = 72


def password_byte_length(password: str) -> int:
    """bcrypt에 전달되는 UTF-8 인코딩 기준 바이트 길이를 반환한다."""
    return len(password.encode("utf-8"))


def validate_bcrypt_password_length(password: str) -> str:
    """bcrypt의 72바이트 입력 제한을 넘는 비밀번호를 거부한다."""
    if password_byte_length(password) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"password must be at most {BCRYPT_MAX_PASSWORD_BYTES} UTF-8 bytes"
        )
    return password


def is_bcrypt_password_length_valid(password: str) -> bool:
    """로그인 검증에서 예외 없이 bcrypt 입력 가능 여부를 확인한다."""
    return password_byte_length(password) <= BCRYPT_MAX_PASSWORD_BYTES
