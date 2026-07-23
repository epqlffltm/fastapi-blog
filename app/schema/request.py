#app/schema/request.py

'''
2026-07-21
refactoring

2026-07-23
회원가입 요청 추가
'''

from pydantic import BaseModel, EmailStr, Field

class ContentCreate(BaseModel):
    nickname: str
    contents: str

class PostCreate(ContentCreate):
    title: str
    image: list[str] = []   # 기본값 빈 리스트 — 안 보내면 이미지 없는 글

class CommentCreate(ContentCreate):
    pass   # nickname, contents만. post_id는 URL에서 받음

class SignUpRequest(BaseModel):
    email: EmailStr                          # 이메일 형식 자동 검증
    password: str = Field(min_length=8, max_length=72)   # bcrypt 72바이트 제한
    nickname: str = Field(min_length=2, max_length=20)