#app/service/auth.py

'''
2026-07-23
인증 서비스 (비밀번호 해싱/검증)
JWT 발급/검증 추가

2026-07-28
bcrypt UTF-8 바이트 제한 검증 / async 라우터용 thread pool 래퍼
JWT token_version 클레임 추가
'''

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from starlette.concurrency import run_in_threadpool

from ..database.connection import settings
from .password import (
    is_bcrypt_password_length_valid,
    validate_bcrypt_password_length,
)


@dataclass(frozen=True, slots=True)
class JWTClaims:
    user_id: int
    token_version: int


class AuthService:
    encoding: str = "UTF-8"
    secret_key: str = settings.jwt_secret_key
    jwt_algorithm: str = settings.jwt_algorithm

    def hash_password(self, plain_password: str) -> str:
        """새 비밀번호를 bcrypt로 해싱한다.

        bcrypt는 UTF-8 인코딩 후 72바이트를 넘는 입력을 처리할 수 없으므로
        호출 경계에서도 검증해 서비스 단독 사용 시의 불변식까지 지킨다.
        """
        validate_bcrypt_password_length(plain_password)
        hashed: bytes = bcrypt.hashpw(
            plain_password.encode(self.encoding),
            salt=bcrypt.gensalt(),
        )
        return hashed.decode(self.encoding)

    async def hash_password_async(self, plain_password: str) -> str:
        """CPU 집약적인 bcrypt 해싱을 이벤트 루프 밖에서 실행한다."""
        return await run_in_threadpool(self.hash_password, plain_password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """평문 비밀번호와 bcrypt 해시가 일치하는지 확인한다.

        로그인 입력은 기존 계정 정책과 독립적으로 받는다. bcrypt 한도를
        넘는 입력은 예외를 내지 않고 일반적인 인증 실패로 처리한다.
        """
        if not is_bcrypt_password_length_valid(plain_password):
            return False
        return bcrypt.checkpw(
            plain_password.encode(self.encoding),
            hashed_password.encode(self.encoding),
        )

    async def verify_password_async(
        self,
        plain_password: str,
        hashed_password: str,
    ) -> bool:
        """CPU 집약적인 bcrypt 검증을 이벤트 루프 밖에서 실행한다."""
        return await run_in_threadpool(
            self.verify_password,
            plain_password,
            hashed_password,
        )

    def create_jwt(self, user_id: int, token_version: int = 0) -> str:
        """사용자와 현재 세션 버전을 담은 액세스 토큰을 발급한다."""
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "sub": str(user_id),
                "ver": int(token_version),
                "iat": now,
                "exp": now + timedelta(seconds=settings.cookie_max_age),
            },
            self.secret_key,
            algorithm=self.jwt_algorithm,
        )

    def decode_jwt_claims(self, access_token: str) -> JWTClaims:
        """JWT를 검증하고 인증에 필요한 클레임을 타입이 보장된 형태로 반환한다."""
        payload: dict = jwt.decode(
            access_token,
            self.secret_key,
            algorithms=[self.jwt_algorithm],
        )
        try:
            user_id = int(payload["sub"])
            # 배포 전에 발급된 토큰에는 ver가 없으므로 0으로 해석한다.
            token_version = int(payload.get("ver", 0))
        except (KeyError, TypeError, ValueError) as exc:
            raise jwt.InvalidTokenError("invalid token claims") from exc

        if user_id <= 0 or token_version < 0:
            raise jwt.InvalidTokenError("invalid token claims")

        return JWTClaims(user_id=user_id, token_version=token_version)

    def decode_jwt(self, access_token: str) -> int:
        """기존 호출부 호환용. 사용자 ID만 반환한다."""
        return self.decode_jwt_claims(access_token).user_id
