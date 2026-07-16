#app/schemas.py

'''
2026-07-16
schemas.py 작성
이미지 필드 리스트로 변경
'''

from pydantic import BaseModel

class ContentCreate(BaseModel):
    nickname: str
    contents: str

class PostCreate(ContentCreate):
    title: str
    image: list[str]      # 이미지 여러 개

class CommentCreate(ContentCreate):
    pass   # nickname, contents만. post_id는 URL에서 받음