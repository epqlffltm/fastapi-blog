#app/service/auth.py

'''
2026-07-23
인증 서비스 (비밀번호 해싱/검증)
JWT 발급/검증 추가

2026-07-28
bcrypt UTF-8 바이트 제한 검증 / async 라우터용 thread pool 래퍼
'''

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from starlette.concurrency import run_in_threadpool

from ..database.connection import settings
from .password import (
    is_bcrypt_password_length_valid,
    validate_bcrypt_password_length,
)


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

    def create_jwt(self, user_id: int) -> str:
        # sub는 JWT 표준상 문자열이어야 한다
        return jwt.encode(
            {
                "sub": str(user_id),
                "exp": datetime.now(timezone.utc) + timedelta(days=1),
            },
            self.secret_key,
            algorithm=self.jwt_algorithm,
        )

    def decode_jwt(self, access_token: str) -> int:
        # 서명이 틀리거나 만료면 예외가 난다 (호출 쪽에서 처리)
        payload: dict = jwt.decode(
            access_token, self.secret_key, algorithms=[self.jwt_algorithm]
        )
        return int(payload["sub"])
