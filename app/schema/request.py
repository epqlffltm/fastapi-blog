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
분류 생성 / 등급 변경
'''

from pydantic import BaseModel, EmailStr, Field
from ..database.orm import UserRole


class ContentCreate(BaseModel):
    contents: str


class PostCreate(ContentCreate):
    title: str
    category_id: int


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


class RoleUpdateRequest(BaseModel):
    role: UserRole      # enum 이라 정해진 값 외에는 스키마에서 걸린다