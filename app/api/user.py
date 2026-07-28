#app/api/user.py

'''
2026-07-23
회원 관련 라우터 (회원가입, 로그인, 내 정보)

2026-07-24
OTP 발급/검증, 비밀번호 재설정
httpOnly 쿠키 로그인 / 로그아웃
회원 목록 · 권한 · 정지 · 강퇴

2026-07-28
프로필 댓글 목록 API 추가
bcrypt 해싱·검증을 thread pool로 이동
OTP 원자 검증·소비 / 비밀번호 변경 시 기존 세션 무효화
아바타 교체 실패·성공 시 고아 파일 정리 / 신뢰 프록시 IP 적용
삭제 글의 댓글이 공개 프로필에 노출되지 않도록 조회 분리
'''

import logging
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, UploadFile,
)
from sqlalchemy.exc import IntegrityError
from ..database.connection import settings
from ..database.orm import User
from ..database.profile_repository import ProfileCommentRepository
from ..database.repository import UserRepository
from ..schema.request import (
    SignUpRequest, LogInRequest, VerifyOTPRequest,
    ResetPasswordRequest, ResetPasswordVerifyRequest,
    PermissionUpdateRequest, SuspendRequest, BanRequest,
    ProfileUpdateRequest, PasswordChangeRequest,
)
from ..schema.response import (
    ListUserSchema, UserSchema, PublicUserSchema,
    ListUserCommentSchema, UserCommentItemSchema, PostBriefSchema, UserBriefSchema,
)
from ..service.auth import AuthService
from ..service.client_ip import get_client_ip
from ..service.upload import UploadService
from ..service.email import EmailService
from ..service.otp import OTPService, OTPVerifyResult
from ..service.ratelimit import LoginRateLimitService
from .dependency import (
    get_current_user, get_active_user, require_permission,
    get_current_user_optional, COOKIE_NAME,
)

router = APIRouter(prefix="/user", tags=["user"])
logger = logging.getLogger(__name__)


def _delete_access_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )


def _require_verified_otp(result: OTPVerifyResult) -> None:
    if result is OTPVerifyResult.VERIFIED:
        return
    if result is OTPVerifyResult.EXPIRED_OR_MISSING:
        raise HTTPException(status_code=400, detail="otp expired or not issued")
    if result is OTPVerifyResult.TOO_MANY_ATTEMPTS:
        raise HTTPException(status_code=429, detail="too many otp attempts")
    raise HTTPException(status_code=400, detail="invalid otp")


@router.post("/sign-up", status_code=201, response_model=UserSchema)
async def sign_up_handler(
    request: SignUpRequest,
    user_repo: UserRepository = Depends(),
    auth_service: AuthService = Depends(),
):
    if await user_repo.get_user_by_email(request.email) is not None:
        raise HTTPException(status_code=409, detail="email already exists")

    if await user_repo.get_user_by_nickname(request.nickname) is not None:
        raise HTTPException(status_code=409, detail="nickname already exists")

    hashed = await auth_service.hash_password_async(request.password)
    user = User.create(
        email=request.email,
        hashed_password=hashed,
        nickname=request.nickname,
    )
    try:
        return await user_repo.save_user(user)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="email or nickname already exists",
        ) from exc


@router.post("/log-in", status_code=200, response_model=UserSchema)
async def log_in_handler(
    request: LogInRequest,
    response: Response,
    http_request: Request,
    user_repo: UserRepository = Depends(),
    auth_service: AuthService = Depends(),
    rate_limit: LoginRateLimitService = Depends(),
):
    ip = get_client_ip(http_request)

    if await rate_limit.is_blocked(request.email, ip):
        raise HTTPException(status_code=429, detail="too many login attempts")

    user = await user_repo.get_user_by_email(request.email)
    if user is None:
        await rate_limit.record_failure(request.email, ip)
        raise HTTPException(status_code=401, detail="invalid email or password")
    if not await auth_service.verify_password_async(request.password, user.password):
        await rate_limit.record_failure(request.email, ip)
        raise HTTPException(status_code=401, detail="invalid email or password")

    await rate_limit.reset(request.email)

    response.set_cookie(
        key=COOKIE_NAME,
        value=auth_service.create_jwt(user.id, token_version=int(user.token_version or 0)),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.cookie_max_age,
        path="/",
    )
    return user


@router.post("/log-out", status_code=200)
async def log_out_handler(response: Response):
    _delete_access_cookie(response)
    return {"message": "logged out"}


@router.get("/me", status_code=200, response_model=UserSchema)
async def get_me_handler(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.patch("/me", status_code=200, response_model=UserSchema)
async def update_me_handler(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(),
):
    nickname_changed = (
        request.nickname is not None
        and request.nickname != current_user.nickname
    )
    if nickname_changed:
        existing = await user_repo.get_user_by_nickname(request.nickname)
        if existing is not None and existing.id != current_user.id:
            raise HTTPException(status_code=409, detail="nickname already exists")
        current_user.nickname = request.nickname

    if request.bio is not None:
        current_user.bio = request.bio

    try:
        return await user_repo.update_user(current_user)
    except IntegrityError as exc:
        if nickname_changed:
            raise HTTPException(
                status_code=409,
                detail="nickname already exists",
            ) from exc
        raise


@router.post("/me/password/otp", status_code=200)
async def send_password_change_otp_handler(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    otp_service: OTPService = Depends(),
    email_service: EmailService = Depends(),
):
    if not await otp_service.acquire_send_slot(current_user.email, purpose="password_change"):
        raise HTTPException(status_code=429, detail="too many requests")

    otp = otp_service.create_otp()
    await otp_service.save_otp(email=current_user.email, otp=otp, purpose="password_change")
    background_tasks.add_task(
        email_service.send_password_reset, current_user.email, otp
    )
    return {"message": "a code has been sent to your email"}


@router.patch("/me/password", status_code=200)
async def change_password_handler(
    request: PasswordChangeRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(),
    auth_service: AuthService = Depends(),
    otp_service: OTPService = Depends(),
):
    if not await auth_service.verify_password_async(
        request.current_password, current_user.password
    ):
        raise HTTPException(status_code=403, detail="current password does not match")

    otp_result = await otp_service.verify_and_consume(
        current_user.email,
        request.otp,
        purpose="password_change",
    )
    _require_verified_otp(otp_result)

    current_user.password = await auth_service.hash_password_async(request.new_password)
    current_user.token_version = int(current_user.token_version or 0) + 1
    await user_repo.update_user(current_user)

    # 현재 쿠키도 즉시 제거하고, 다른 브라우저의 토큰은 token_version 비교로 거부한다.
    _delete_access_cookie(response)
    return {"message": "password changed"}


@router.post("/me/avatar", status_code=200, response_model=UserSchema)
async def upload_avatar_handler(
    file: UploadFile,
    current_user: User = Depends(get_active_user),
    user_repo: UserRepository = Depends(),
    upload_service: UploadService = Depends(),
):
    previous_url = current_user.avatar_url
    previous_filename = upload_service.managed_filename_from_url(previous_url)

    filename, _size = await upload_service.save(file)
    current_user.avatar_url = f"/img/{filename}"

    try:
        updated_user = await user_repo.update_user(current_user)
    except Exception:
        # DB 반영에 실패하면 새 파일이 고아가 되지 않도록 제거하고 메모리 상태도 복구한다.
        current_user.avatar_url = previous_url
        with suppress(OSError, ValueError):
            await upload_service.delete(filename)
        raise

    # DB가 새 URL을 확정한 뒤에만 이전 로컬 아바타를 지운다. 삭제 실패는
    # 프로필 변경 성공을 되돌릴 이유가 없으므로 로그만 남긴다.
    if previous_filename is not None and previous_filename != filename:
        try:
            await upload_service.delete(previous_filename)
        except (OSError, ValueError):
            logger.exception(
                "old avatar cleanup failed",
                extra={"user_id": current_user.id, "filename": previous_filename},
            )

    return updated_user


@router.get("/{id}/profile", status_code=200, response_model=PublicUserSchema)
async def get_public_profile_handler(
    id: int,
    user_repo: UserRepository = Depends(),
):
    user = await user_repo.get_user_by_id(id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@router.get("/{id}/comments", status_code=200, response_model=ListUserCommentSchema)
async def get_user_comments_handler(
    id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=50),
    viewer: User | None = Depends(get_current_user_optional),
    comment_repo: ProfileCommentRepository = Depends(),
    user_repo: UserRepository = Depends(),
):
    user = await user_repo.get_user_by_id(id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    include_deleted = viewer is not None and viewer.can_manage_post

    rows, total = await comment_repo.get_comments_by_user(
        user_id=id,
        page=page,
        size=size,
        include_deleted=include_deleted,
    )

    items = []
    for comment, post in rows:
        items.append(
            UserCommentItemSchema(
                id=comment.id,
                contents=comment.contents,
                is_deleted=comment.is_deleted,
                created_at=comment.created_at,
                parent_id=comment.parent_id,
                post=PostBriefSchema.model_validate(post),
                parent_user=None,
            )
        )

    total_pages = (total + size - 1) // size if size else 0
    return ListUserCommentSchema(
        comments=items,
        page=page,
        size=size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/list", status_code=200, response_model=ListUserSchema)
async def get_users_handler(
    current_user: User = Depends(require_permission("can_manage_user")),
    user_repo: UserRepository = Depends(),
):
    users = await user_repo.get_users()
    return ListUserSchema(users=users)


@router.patch("/{id}/permissions", status_code=200, response_model=UserSchema)
async def update_permissions_handler(
    id: int,
    request: PermissionUpdateRequest,
    current_user: User = Depends(require_permission("can_manage_user")),
    user_repo: UserRepository = Depends(),
):
    if id == current_user.id:
        raise HTTPException(status_code=400, detail="cannot change your own permissions")

    user = await user_repo.get_user_by_id(id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    for name, value in request.model_dump(exclude_none=True).items():
        setattr(user, name, value)

    return await user_repo.update_user(user)


@router.patch("/{id}/suspend", status_code=200, response_model=UserSchema)
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


@router.patch("/{id}/ban", status_code=200, response_model=UserSchema)
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


@router.post("/email/otp", status_code=200)
async def create_otp_handler(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    otp_service: OTPService = Depends(),
    email_service: EmailService = Depends(),
):
    if current_user.is_verified:
        raise HTTPException(status_code=409, detail="already verified")
    if not await otp_service.acquire_send_slot(current_user.email, purpose="signup"):
        raise HTTPException(status_code=429, detail="too many requests")

    otp = otp_service.create_otp()
    await otp_service.save_otp(email=current_user.email, otp=otp, purpose="signup")

    background_tasks.add_task(email_service.send_otp, current_user.email, otp)

    return {"email": current_user.email, "expires_in": otp_service.ttl}


@router.post("/email/otp/verify", status_code=200, response_model=UserSchema)
async def verify_otp_handler(
    request: VerifyOTPRequest,
    current_user: User = Depends(get_current_user),
    otp_service: OTPService = Depends(),
    user_repo: UserRepository = Depends(),
):
    otp_result = await otp_service.verify_and_consume(
        current_user.email,
        request.otp,
        purpose="signup",
    )
    _require_verified_otp(otp_result)

    current_user.is_verified = True
    await user_repo.update_user(current_user)
    return current_user


@router.post("/password/reset", status_code=200)
async def reset_password_handler(
    request: ResetPasswordRequest,
    background_tasks: BackgroundTasks,
    user_repo: UserRepository = Depends(),
    otp_service: OTPService = Depends(),
    email_service: EmailService = Depends(),
):
    user = await user_repo.get_user_by_email(request.email)
    if user is not None and await otp_service.acquire_send_slot(request.email, purpose="reset"):
        otp = otp_service.create_otp()
        await otp_service.save_otp(email=request.email, otp=otp, purpose="reset")
        background_tasks.add_task(
            email_service.send_password_reset, request.email, otp
        )

    return {"message": "if the email exists, a code has been sent"}


@router.post("/password/reset/verify", status_code=200)
async def reset_password_verify_handler(
    request: ResetPasswordVerifyRequest,
    user_repo: UserRepository = Depends(),
    otp_service: OTPService = Depends(),
    auth_service: AuthService = Depends(),
):
    otp_result = await otp_service.verify_and_consume(
        request.email,
        request.otp,
        purpose="reset",
    )
    _require_verified_otp(otp_result)

    user = await user_repo.get_user_by_email(request.email)
    if user is None:
        raise HTTPException(status_code=400, detail="invalid otp")

    user.password = await auth_service.hash_password_async(request.new_password)
    user.token_version = int(user.token_version or 0) + 1
    await user_repo.update_user(user)
    return {"message": "password changed"}
