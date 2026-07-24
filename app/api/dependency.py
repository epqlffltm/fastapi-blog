#app/api/dependency.py

'''
2026-07-23
인증 의존성 (요청 헤더의 토큰 → User)

2026-07-24
인증된 유저 의존성 추가
2026-07-24
httpOnly 쿠키에서 토큰을 읽도록 변경
'''

import jwt
from fastapi import Cookie, Depends, HTTPException
from ..database.orm import User
from ..database.repository import UserRepository
from ..service.auth import AuthService

COOKIE_NAME = "access_token"


def get_access_token(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> str:
    # JS가 읽을 수 없는 httpOnly 쿠키에서 꺼낸다
    if access_token is None:
        raise HTTPException(status_code=401, detail="not authorized")
    return access_token


def get_current_user(
    access_token: str = Depends(get_access_token),
    auth_service: AuthService = Depends(),
    user_repo: UserRepository = Depends(),
) -> User:
    try:
        user_id = auth_service.decode_jwt(access_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid token")

    user = user_repo.get_user_by_id(user_id)
    if user is None:      # 토큰은 유효한데 계정이 사라진 경우
        raise HTTPException(status_code=401, detail="user not found")
    return user


def get_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="email not verified")
    return current_user