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
'''

from pydantic import BaseModel, EmailStr, Field


class ContentCreate(BaseModel):
    contents: str


class PostCreate(ContentCreate):
    title: str
    category_id: int


class CommentCreate(ContentCreate):
    pass


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