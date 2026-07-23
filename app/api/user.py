#app/api/user.py

'''
2026-07-23
회원 관련 라우터 (회원가입)
'''

from fastapi import APIRouter, Depends, HTTPException
from ..database.repository import UserRepository
from ..database.orm import User
from ..schema.request import SignUpRequest
from ..schema.response import UserSchema
from ..service.auth import AuthService

router = APIRouter(prefix="/user", tags=["user"])


@router.post("/sign-up", status_code=201, response_model=UserSchema)#회원가입
def sign_up_handler(
    request: SignUpRequest,
    user_repo: UserRepository = Depends(),
    auth_service: AuthService = Depends(),
):
    # 이메일 중복 확인
    if user_repo.get_user_by_email(request.email) is not None:
        raise HTTPException(status_code=409, detail="email already exists")

    # 닉네임 중복 확인
    if user_repo.get_user_by_nickname(request.nickname) is not None:
        raise HTTPException(status_code=409, detail="nickname already exists")

    hashed = auth_service.hash_password(request.password)   # 평문 저장 금지
    user = User.create(
        email=request.email,
        hashed_password=hashed,
        nickname=request.nickname,
    )
    user = user_repo.save_user(user)
    return user