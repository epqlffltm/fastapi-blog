#app/api/user.py

'''
2026-07-23
회원 관련 라우터 (회원가입)
로그인 + 내 정보

2026-07-24
엔드포인트 2개 추가
create_otp_handler 교체
'''

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from ..database.repository import UserRepository
from ..database.orm import User
from ..service.auth import AuthService
from ..schema.response import UserSchema, JWTResponse
from .dependency import get_current_user
from ..schema.request import SignUpRequest, LogInRequest, VerifyOTPRequest, ResetPasswordRequest, ResetPasswordVerifyRequest
from ..service.otp import OTPService
from ..service.email import EmailService

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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    otp_service: OTPService = Depends(),
    email_service: EmailService = Depends(),
):
    if current_user.is_verified:
        raise HTTPException(status_code=409, detail="already verified")
    if not otp_service.start_cooldown(current_user.email, purpose="signup"):
        raise HTTPException(status_code=429, detail="too many requests")

    otp = otp_service.create_otp()
    otp_service.save_otp(email=current_user.email, otp=otp, purpose="signup")

    # 메일 발송은 느리므로 응답을 먼저 보내고 뒤에서 처리
    background_tasks.add_task(email_service.send_otp, current_user.email, otp)

    return {"email": current_user.email, "expires_in": otp_service.ttl}


@router.post("/email/otp/verify", status_code=200, response_model=UserSchema)#인증코드 검증
def verify_otp_handler(
    request: VerifyOTPRequest,
    current_user: User = Depends(get_current_user),
    otp_service: OTPService = Depends(),
    user_repo: UserRepository = Depends(),
):
    saved = otp_service.get_otp(current_user.email, purpose="signup")
    if saved is None:      # 발급 안 했거나 3분이 지나 만료됨
        raise HTTPException(status_code=400, detail="otp expired or not issued")
    if saved != request.otp:
        raise HTTPException(status_code=400, detail="invalid otp")

    current_user.is_verified = True
    user_repo.update_user(current_user)
    otp_service.delete_otp(current_user.email, purpose="signup")   # 1회용이므로 즉시 폐기

    return current_user

@router.post("/password/reset", status_code=200)#비번 재설정 코드 발송
def reset_password_handler(
    request: ResetPasswordRequest,
    background_tasks: BackgroundTasks,
    user_repo: UserRepository = Depends(),
    otp_service: OTPService = Depends(),
    email_service: EmailService = Depends(),
):
    # 계정이 없어도 있는 것처럼 응답한다 (가입 여부 노출 방지)
    user = user_repo.get_user_by_email(request.email)
    if user is not None and otp_service.start_cooldown(request.email, purpose="reset"):
        otp = otp_service.create_otp()
        otp_service.save_otp(email=request.email, otp=otp, purpose="reset")
        background_tasks.add_task(
            email_service.send_password_reset, request.email, otp
        )

    return {"message": "if the email exists, a code has been sent"}


@router.post("/password/reset/verify", status_code=200)#비번 재설정 실행
def reset_password_verify_handler(
    request: ResetPasswordVerifyRequest,
    user_repo: UserRepository = Depends(),
    otp_service: OTPService = Depends(),
    auth_service: AuthService = Depends(),
):
    saved = otp_service.get_otp(request.email, purpose="reset")
    if saved is None:
        raise HTTPException(status_code=400, detail="otp expired or not issued")
    if saved != request.otp:
        raise HTTPException(status_code=400, detail="invalid otp")

    user = user_repo.get_user_by_email(request.email)
    if user is None:      # 코드 발급 후 탈퇴한 경우
        raise HTTPException(status_code=400, detail="invalid otp")

    user.password = auth_service.hash_password(request.new_password)
    user_repo.update_user(user)
    otp_service.delete_otp(request.email, purpose="reset")

    return {"message": "password changed"}