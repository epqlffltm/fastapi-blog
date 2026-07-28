#app/schema/request.py

'''
2026-07-21
refactoring

2026-07-23
회원가입/로그인 요청
nickname 제거 (작성자는 토큰에서)

2026-07-24
글 작성에 category_id 추가
이미지는 본문(마크다운)에 들어가므로 image 필드 제거
댓글에 parent_id 추가 (대댓글)
분류 생성 / 권한 · 정지 · 강퇴

2026-07-25
분류 이름 변경 / 글 분류 이동

2026-07-26
프로필 수정(닉네임·소개)
'''

from pydantic import BaseModel, EmailStr, Field, field_validator


class ContentCreate(BaseModel):
    contents: str


class PostCreate(ContentCreate):
    title: str = Field(min_length=1, max_length=200)
    contents: str = Field(min_length=1, max_length=100_000)
    category_id: int

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        # 제목 앞뒤 공백은 저장하지 않고, 공백만 있는 제목은 거부한다
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @field_validator("contents")
    @classmethod
    def validate_contents(cls, value: str) -> str:
        # 마크다운 원문은 보존하되 공백만 있는 본문은 거부한다
        if not value.strip():
            raise ValueError("contents must not be blank")
        return value


class CommentCreate(ContentCreate):
    parent_id: int | None = None     # 없으면 원댓글, 있으면 그 댓글의 답글


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)   # bcrypt 72바이트 제한
    nickname: str = Field(min_length=2, max_length=20)


class LogInRequest(BaseModel):
    # 로그인엔 길이 제한을 걸지 않는다. 정책이 바뀌면 기존 회원이 갇힌다
    email: EmailStr
    password: str


class VerifyOTPRequest(BaseModel):
    otp: int = Field(ge=100_000, le=999_999)


class ResetPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordVerifyRequest(BaseModel):
    email: EmailStr
    otp: int = Field(ge=100_000, le=999_999)
    new_password: str = Field(min_length=8, max_length=72)


class CategoryCreate(BaseModel):
    # slug 는 URL 에 들어가므로 영소문자·숫자·하이픈만. 한글이면 인코딩돼 지저분해진다
    slug: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=32)
    display_order: int = 0


class CategoryUpdate(BaseModel):
    # slug 는 URL 에 박혀 있어 바꾸면 링크가 깨지므로 이름만 변경 대상
    name: str = Field(min_length=1, max_length=32)


class PostCategoryUpdate(BaseModel):
    # 글을 다른 분류로 옮긴다 (관리자 전용, 미분류 청소용)
    category_id: int


class PermissionUpdateRequest(BaseModel):
    # 전부 선택. 체크박스 하나를 눌러도 그 하나만 보내면 된다
    can_comment: bool | None = None
    can_write_post: bool | None = None
    can_upload: bool | None = None
    can_manage_category: bool | None = None
    can_manage_user: bool | None = None
    can_manage_post: bool | None = None


class SuspendRequest(BaseModel):
    days: int = Field(ge=0, le=3650)      # 0 이면 정지 해제


class BanRequest(BaseModel):
    banned: bool


class ProfileUpdateRequest(BaseModel):
    # 둘 다 선택 — 보낸 것만 바뀐다. bio 는 ""이면 소개를 지우는 것
    nickname: str | None = Field(default=None, min_length=2, max_length=20)   # 가입과 동일 규칙
    bio: str | None = Field(default=None, max_length=500)


class PasswordChangeRequest(BaseModel):
    current_password: str                                     # 본인 확인용 (비번 유출 방어)
    new_password: str = Field(min_length=8, max_length=72)   # bcrypt 72바이트 제한
    otp: int = Field(ge=100_000, le=999_999)                 # 이메일로 받은 6자리 (계정 탈취 방어)