#app/api/user.py

'''
2026-07-23
회원 관련 라우터 (회원가입, 로그인, 내 정보)

2026-07-24
OTP 발급/검증, 비밀번호 재설정
httpOnly 쿠키 로그인 / 로그아웃
회원 목록 · 권한 · 정지 · 강퇴
'''

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, UploadFile
from ..database.connection import settings
from ..database.orm import User
from ..database.repository import UserRepository
from ..schema.request import (
    SignUpRequest, LogInRequest, VerifyOTPRequest,
    ResetPasswordRequest, ResetPasswordVerifyRequest,
    PermissionUpdateRequest, SuspendRequest, BanRequest,
    ProfileUpdateRequest, PasswordChangeRequest,
)
from ..schema.response import ListUserSchema, UserSchema, PublicUserSchema
from ..service.auth import AuthService
from ..service.upload import UploadService
from ..service.email import EmailService
from ..service.otp import OTPService
from .dependency import get_current_user, get_active_user, require_permission, COOKIE_NAME

router = APIRouter(prefix="/user", tags=["user"])


@router.post("/sign-up", status_code=201, response_model=UserSchema)#회원가입
async def sign_up_handler(
    request: SignUpRequest,
    user_repo: UserRepository = Depends(),
    auth_service: AuthService = Depends(),
):
    # 이메일 중복 확인
    if await user_repo.get_user_by_email(request.email) is not None:
        raise HTTPException(status_code=409, detail="email already exists")

    # 닉네임 중복 확인
    if await user_repo.get_user_by_nickname(request.nickname) is not None:
        raise HTTPException(status_code=409, detail="nickname already exists")

    hashed = auth_service.hash_password(request.password)   # 평문 저장 금지
    user = User.create(
        email=request.email,
        hashed_password=hashed,
        nickname=request.nickname,
    )
    user = await user_repo.save_user(user)
    return user


@router.post("/log-in", status_code=200, response_model=UserSchema)#로그인
async def log_in_handler(
    request: LogInRequest,
    response: Response,
    user_repo: UserRepository = Depends(),
    auth_service: AuthService = Depends(),
):
    user = await user_repo.get_user_by_email(request.email)
    # 이메일이 없든 비번이 틀리든 같은 메시지 (계정 존재 여부 노출 방지)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid email or password")
    if not auth_service.verify_password(request.password, user.password):
        raise HTTPException(status_code=401, detail="invalid email or password")

    # 제재된 계정도 로그인은 시킨다. 본인이 상태를 확인할 수 있어야 한다
    response.set_cookie(
        key=COOKIE_NAME,
        value=auth_service.create_jwt(user.id),
        httponly=True,                      # JS가 읽을 수 없다 (XSS 방어)
        secure=settings.cookie_secure,      # HTTPS 전용 (배포 시 true)
        samesite="strict",                  # 다른 사이트발 요청엔 안 붙는다 (CSRF 방어)
        max_age=settings.cookie_max_age,
        path="/",
    )
    return user       # 프론트가 권한·제재 상태를 바로 쓸 수 있게 회원 정보를 반환


@router.post("/log-out", status_code=200)#로그아웃
async def log_out_handler(response: Response):
    # 쿠키를 지울 때도 발급 때와 같은 속성을 줘야 브라우저가 같은 쿠키로 인식한다
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return {"message": "logged out"}


@router.get("/me", status_code=200, response_model=UserSchema)#내 정보
async def get_me_handler(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.patch("/me", status_code=200, response_model=UserSchema)#내 정보 수정
async def update_me_handler(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(),
):
    # 닉네임을 바꾸면 다른 사람이 이미 쓰는지 확인한다 (자기 자신은 예외)
    if request.nickname is not None and request.nickname != current_user.nickname:
        existing = await user_repo.get_user_by_nickname(request.nickname)
        if existing is not None and existing.id != current_user.id:
            raise HTTPException(status_code=409, detail="nickname already exists")
        current_user.nickname = request.nickname

    # bio 는 빈 문자열이면 소개를 지우는 것. None 이면 안 건드린다
    if request.bio is not None:
        current_user.bio = request.bio

    return await user_repo.update_user(current_user)


@router.post("/me/password/otp", status_code=200)#비밀번호 변경용 코드 발송
async def send_password_change_otp_handler(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    otp_service: OTPService = Depends(),
    email_service: EmailService = Depends(),
):
    # 로그인된 본인의 이메일로만 보낸다 (요청에서 이메일을 안 받아, 남의 주소로 못 보냄)
    if otp_service.start_cooldown(current_user.email, purpose="password_change"):
        otp = otp_service.create_otp()
        otp_service.save_otp(email=current_user.email, otp=otp, purpose="password_change")
        background_tasks.add_task(
            email_service.send_password_reset, current_user.email, otp
        )
    return {"message": "a code has been sent to your email"}


@router.patch("/me/password", status_code=200)#비밀번호 변경 (현재 비번 + 이메일 OTP)
async def change_password_handler(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(),
    auth_service: AuthService = Depends(),
    otp_service: OTPService = Depends(),
):
    # 1) 현재 비번 확인 — 비번이 유출돼도 현재 비번을 모르면 막힌다
    if not auth_service.verify_password(request.current_password, current_user.password):
        raise HTTPException(status_code=403, detail="current password does not match")

    # 2) 이메일 OTP 확인 — 비번을 알고 로그인했어도 이메일 계정까지 못 뚫으면 막힌다 (2차 인증)
    saved = otp_service.get_otp(current_user.email, purpose="password_change")
    if saved is None:
        raise HTTPException(status_code=400, detail="otp expired or not issued")
    if saved != request.otp:
        raise HTTPException(status_code=400, detail="invalid otp")

    current_user.password = auth_service.hash_password(request.new_password)
    await user_repo.update_user(current_user)
    otp_service.delete_otp(current_user.email, purpose="password_change")   # 재사용 방지
    return {"message": "password changed"}


@router.post("/me/avatar", status_code=200, response_model=UserSchema)#프로필 이미지 업로드
async def upload_avatar_handler(
    file: UploadFile,
    # 자기 프로필 이미지라 can_upload(글 이미지용) 대신 로그인+정상 회원이면 허용
    current_user: User = Depends(get_active_user),
    user_repo: UserRepository = Depends(),
    upload_service: UploadService = Depends(),
):
    # 저장·검증(타입/크기)은 글 이미지와 같은 서비스를 재활용한다
    filename, _size = await upload_service.save(file)
    current_user.avatar_url = f"/img/{filename}"
    return await user_repo.update_user(current_user)


@router.get("/{id}/profile", status_code=200, response_model=PublicUserSchema)#남의 공개 프로필
async def get_public_profile_handler(
    id: int,
    user_repo: UserRepository = Depends(),
):
    # 로그인 불필요(공개). 공개 정보만 담은 PublicUserSchema 로 응답 → 이메일·권한은 안 새어나간다
    user = await user_repo.get_user_by_id(id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@router.get("/list", status_code=200, response_model=ListUserSchema)#회원 목록
async def get_users_handler(
    current_user: User = Depends(require_permission("can_manage_user")),
    user_repo: UserRepository = Depends(),
):
    users = await user_repo.get_users()
    return ListUserSchema(users=users)


@router.patch("/{id}/permissions", status_code=200, response_model=UserSchema)#권한 변경
async def update_permissions_handler(
    id: int,
    request: PermissionUpdateRequest,
    current_user: User = Depends(require_permission("can_manage_user")),
    user_repo: UserRepository = Depends(),
):
    # 자기 권한은 못 바꾼다. 마지막 관리자가 스스로 내리면 아무도 되돌릴 수 없다
    if id == current_user.id:
        raise HTTPException(status_code=400, detail="cannot change your own permissions")

    user = await user_repo.get_user_by_id(id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    # 보내온 항목만 반영한다 (None 은 "안 건드림")
    for name, value in request.model_dump(exclude_none=True).items():
        setattr(user, name, value)

    return await user_repo.update_user(user)


@router.patch("/{id}/suspend", status_code=200, response_model=UserSchema)#정지
async def suspend_handler(
    id: int,
    request: SuspendRequest,
    current_user: User = Depends(require_permission("can_manage_user")),
    user_repo: UserRepository = Depends(),
):
    if id == current_user.id:
        raise HTTPException(status_code=400, detail="cannot suspend yourself")

    user = await user_repo.get_user_by_id(id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    user.suspended_until = (
        None if request.days == 0
        else datetime.now(timezone.utc) + timedelta(days=request.days)
    )
    return await user_repo.update_user(user)


@router.patch("/{id}/ban", status_code=200, response_model=UserSchema)#강퇴
async def ban_handler(
    id: int,
    request: BanRequest,
    current_user: User = Depends(require_permission("can_manage_user")),
    user_repo: UserRepository = Depends(),
):
    if id == current_user.id:
        raise HTTPException(status_code=400, detail="cannot ban yourself")

    user = await user_repo.get_user_by_id(id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    user.is_banned = request.banned
    return await user_repo.update_user(user)


@router.post("/email/otp", status_code=200)#인증코드 발급
async def create_otp_handler(
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
async def verify_otp_handler(
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
    await user_repo.update_user(current_user)
    otp_service.delete_otp(current_user.email, purpose="signup")   # 1회용이므로 즉시 폐기

    return current_user


@router.post("/password/reset", status_code=200)#비번 재설정 코드 발송
async def reset_password_handler(
    request: ResetPasswordRequest,
    background_tasks: BackgroundTasks,
    user_repo: UserRepository = Depends(),
    otp_service: OTPService = Depends(),
    email_service: EmailService = Depends(),
):
    # 계정이 없어도 있는 것처럼 응답한다 (가입 여부 노출 방지)
    user = await user_repo.get_user_by_email(request.email)
    if user is not None and otp_service.start_cooldown(request.email, purpose="reset"):
        otp = otp_service.create_otp()
        otp_service.save_otp(email=request.email, otp=otp, purpose="reset")
        background_tasks.add_task(
            email_service.send_password_reset, request.email, otp
        )

    return {"message": "if the email exists, a code has been sent"}


@router.post("/password/reset/verify", status_code=200)#비번 재설정 실행
async def reset_password_verify_handler(
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

    user = await user_repo.get_user_by_email(request.email)
    if user is None:      # 코드 발급 후 탈퇴한 경우
        raise HTTPException(status_code=400, detail="invalid otp")

    user.password = auth_service.hash_password(request.new_password)
    await user_repo.update_user(user)
    otp_service.delete_otp(request.email, purpose="reset")

    return {"message": "password changed"}