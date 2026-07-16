#app/schemas.py

'''
2026-07-16
schemas.py 작성
'''

from pydantic import BaseModel

class ContentCreate(BaseModel):
    nickname: str
    contents: str

class PostCreate(ContentCreate):
    title: str
    image: str

class CommentCreate(ContentCreate):
    pass   # nickname, contents만. post_id는 URL에서 받음