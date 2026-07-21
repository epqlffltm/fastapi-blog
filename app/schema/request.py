#app/schema/request.py

'''
2026-07-21
refactoring
'''

from pydantic import BaseModel

class ContentCreate(BaseModel):
    nickname: str
    contents: str

class PostCreate(ContentCreate):
    title: str
    image: list[str] = []   # 기본값 빈 리스트 — 안 보내면 이미지 없는 글

class CommentCreate(ContentCreate):
    pass   # nickname, contents만. post_id는 URL에서 받음