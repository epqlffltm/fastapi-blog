#app/schema/request.py

'''
2026-07-21
refactoring

2026-07-23
회원가입/로그인 요청
nickname 제거 (작성자는 토큰에서)

2026-07-24
비번 변경 스키마 추가
'''

from pydantic import BaseModel, EmailStr, Field


class ContentCreate(BaseModel):
    contents: str


class PostCreate(ContentCreate):
    title: str
    image: list[str] = []


class CommentCreate(ContentCreate):
    pass


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    nickname: str = Field(min_length=2, max_length=20)


class LogInRequest(BaseModel):
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