#app/api/dependency.py

'''
2026-07-23
인증 의존성 (요청 헤더의 토큰 → User)

2026-07-24
httpOnly 쿠키에서 토큰을 읽도록 변경
등급 확인 → 권한 체크박스 / 제재(정지·강퇴)로 전환

2026-07-28
JWT token_version과 DB 값을 비교해 기존 세션 무효화
'''

import jwt
from fastapi import Cookie, Depends, HTTPException

from ..database.orm import PERMISSION_NAMES, User
from ..database.repository import UserRepository
from ..service.auth import AuthService, JWTClaims

COOKIE_NAME = "access_token"


def get_access_token(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> str:
    if access_token is None:
        raise HTTPException(status_code=401, detail="not authorized")
    return access_token


def _session_version_matches(claims: JWTClaims, user: User) -> bool:
    return claims.token_version == int(user.token_version or 0)


async def get_current_user(
    access_token: str = Depends(get_access_token),
    auth_service: AuthService = Depends(),
    user_repo: UserRepository = Depends(),
) -> User:
    try:
        claims = auth_service.decode_jwt_claims(access_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid token")

    user = await user_repo.get_user_by_id(claims.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    if not _session_version_matches(claims, user):
        raise HTTPException(status_code=401, detail="session expired")
    return user


async def get_current_user_optional(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    auth_service: AuthService = Depends(),
    user_repo: UserRepository = Depends(),
) -> User | None:
    if access_token is None:
        return None
    try:
        claims = auth_service.decode_jwt_claims(access_token)
    except jwt.PyJWTError:
        return None

    user = await user_repo.get_user_by_id(claims.user_id)
    if user is None or not _session_version_matches(claims, user):
        return None
    return user


async def get_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="email not verified")
    return current_user


async def get_active_user(
    current_user: User = Depends(get_verified_user),
) -> User:
    if current_user.is_banned:
        raise HTTPException(status_code=403, detail="banned")
    if current_user.is_suspended:
        raise HTTPException(status_code=403, detail="suspended")
    return current_user


def require_permission(permission: str):
    assert permission in PERMISSION_NAMES, f"unknown permission: {permission}"

    def dependency(
        current_user: User = Depends(get_active_user),
    ) -> User:
        if not getattr(current_user, permission):
            raise HTTPException(
                status_code=403, detail=f"permission denied: {permission}"
            )
        return current_user

    return dependency
