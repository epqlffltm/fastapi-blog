#app/api/dependency.py

'''
2026-07-23
인증 의존성 (요청 헤더의 토큰 → User)

2026-07-24
httpOnly 쿠키에서 토큰을 읽도록 변경
등급 확인 → 권한 체크박스 / 제재(정지·강퇴)로 전환
'''

import jwt
from fastapi import Cookie, Depends, HTTPException
from ..database.orm import User, PERMISSION_NAMES
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


async def get_current_user(
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

    user = await user_repo.get_user_by_id(user_id)
    if user is None:      # 토큰은 유효한데 계정이 사라진 경우
        raise HTTPException(status_code=401, detail="user not found")
    return user

async def get_current_user_optional(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    auth_service: AuthService = Depends(),
    user_repo: UserRepository = Depends(),
) -> User | None:
    # 공개 페이지용. 토큰이 없거나 이상하면 401 대신 그냥 None (비로그인 취급)
    if access_token is None:
        return None
    try:
        user_id = auth_service.decode_jwt(access_token)
    except jwt.PyJWTError:      # 만료(ExpiredSignatureError 포함)도 여기 잡힌다
        return None
    return await user_repo.get_user_by_id(user_id)


async def get_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    # 401(누구인지 모름)과 403(누구인지는 알지만 자격 없음)을 구분한다
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="email not verified")
    return current_user


async def get_active_user(
    current_user: User = Depends(get_verified_user),
) -> User:
    # 인증 → 이메일 확인 다음. 제재된 계정은 새 내용을 만들 수 없다.
    # 강퇴가 정지보다 무거우므로 먼저 본다
    if current_user.is_banned:
        raise HTTPException(status_code=403, detail="banned")
    if current_user.is_suspended:        # 기한이 지났으면 property가 알아서 False
        raise HTTPException(status_code=403, detail="suspended")
    return current_user


def require_permission(permission: str):
    # 라우터가 데코레이터에서 부르므로, 권한 이름 오타는 서버 기동 시점에 바로 걸린다
    assert permission in PERMISSION_NAMES, f"unknown permission: {permission}"

    def dependency(
        current_user: User = Depends(get_active_user),
    ) -> User:
        # 게이트 순서: 인증 → 이메일 → 제재 → 권한
        if not getattr(current_user, permission):
            raise HTTPException(
                status_code=403, detail=f"permission denied: {permission}"
            )
        return current_user

    return dependency