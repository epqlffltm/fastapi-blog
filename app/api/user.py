#app/api/user.py

'''
2026-07-23
회원 관련 라우터 (회원가입)
로그인 + 내 정보

2026-07-24
엔드포인트 2개 추가
'''

from fastapi import APIRouter, Depends, HTTPException
from ..database.repository import UserRepository
from ..database.orm import User
from ..service.auth import AuthService
from ..schema.response import UserSchema, JWTResponse
from .dependency import get_current_user
from ..schema.request import SignUpRequest, LogInRequest, VerifyOTPRequest
from ..service.otp import OTPService

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

@router.post("/log-in", status_code=200, response_model=JWTResponse)#로그인
def log_in_handler(
    request: LogInRequest,
    user_repo: UserRepository = Depends(),
    auth_service: AuthService = Depends(),
):
    user = user_repo.get_user_by_email(request.email)
    # 이메일이 없든 비번이 틀리든 같은 메시지 (계정 존재 여부 노출 방지)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid email or password")
    if not auth_service.verify_password(request.password, user.password):
        raise HTTPException(status_code=401, detail="invalid email or password")

    return JWTResponse(access_token=auth_service.create_jwt(user.id))


@router.get("/me", status_code=200, response_model=UserSchema)#내 정보
def get_me_handler(
    current_user: User = Depends(get_current_user),
):
    return current_user

@router.post("/email/otp", status_code=200)#인증코드 발급
def create_otp_handler(
    current_user: User = Depends(get_current_user),
    otp_service: OTPService = Depends(),
):
    if current_user.is_verified:
        raise HTTPException(status_code=409, detail="already verified")

    otp = otp_service.create_otp()
    otp_service.save_otp(email=current_user.email, otp=otp)

    print(f"[OTP] {current_user.email} → {otp}")   # 이메일 발송 붙이기 전 임시 확인용

    # TODO: 이메일 발송 붙이면 otp는 응답에서 제거할 것
    return {"email": current_user.email, "otp": otp, "expires_in": otp_service.ttl}


@router.post("/email/otp/verify", status_code=200, response_model=UserSchema)#인증코드 검증
def verify_otp_handler(
    request: VerifyOTPRequest,
    current_user: User = Depends(get_current_user),
    otp_service: OTPService = Depends(),
    user_repo: UserRepository = Depends(),
):
    saved = otp_service.get_otp(current_user.email)
    if saved is None:      # 발급 안 했거나 3분이 지나 만료됨
        raise HTTPException(status_code=400, detail="otp expired or not issued")
    if saved != request.otp:
        raise HTTPException(status_code=400, detail="invalid otp")

    current_user.is_verified = True
    user_repo.update_user(current_user)
    otp_service.delete_otp(current_user.email)   # 1회용이므로 즉시 폐기

    return current_user