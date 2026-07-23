#app/service/auth.py

'''
2026-07-23
인증 서비스 (비밀번호 해싱/검증)
JWT 발급/검증 추가
'''

import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from ..database.connection import settings


class AuthService:
    encoding: str = "UTF-8"
    secret_key: str = settings.jwt_secret_key
    jwt_algorithm: str = settings.jwt_algorithm

    def hash_password(self, plain_password: str) -> str:
        # bcrypt는 salt를 자동 생성해서 해시에 포함시킨다
        hashed: bytes = bcrypt.hashpw(
            plain_password.encode(self.encoding),
            salt=bcrypt.gensalt(),
        )
        return hashed.decode(self.encoding)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        # 해시에 salt가 들어있어서 별도 salt 전달이 필요 없다
        return bcrypt.checkpw(
            plain_password.encode(self.encoding),
            hashed_password.encode(self.encoding),
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