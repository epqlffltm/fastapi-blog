#app/service/auth.py

'''
2026-07-23
인증 서비스 (비밀번호 해싱/검증)
'''

import bcrypt


class AuthService:
    encoding: str = "UTF-8"

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