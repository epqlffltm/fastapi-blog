#app/schema/response.py

'''
2026-07-20
orm → http response 스키마
'''

from pydantic import BaseModel, ConfigDict
from datetime import datetime


# 목록의 글 하나 (댓글 수 포함)
class PostListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    nickname: str
    created_at: datetime
    comment_count: int


# 목록 전체 (위 항목들의 리스트)
class ListPostSchema(BaseModel):
    posts: list[PostListItemSchema]      # PostSchema → PostListItemSchema로