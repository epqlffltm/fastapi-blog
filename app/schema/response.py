#app/schema/response.py

'''
2026-07-20
orm → http response 스키마
get 단일 조회 api

2026-07-23
회원 응답 추가
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
    
# 댓글 하나의 스키마
class CommentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nickname: str
    contents: str
    created_at: datetime

# 이미지 하나의 스키마
class ImageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    display_order: int

# 글 상세 (댓글 + 이미지를 품음)
class PostDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    nickname: str
    contents: str
    created_at: datetime
    updated_at: datetime
    comments: list[CommentSchema]      # 댓글들 중첩
    images: list[ImageSchema]          # 이미지들 중첩
    
class UserSchema(BaseModel): #회원 응답 추가
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nickname: str
    is_verified: bool
    # password는 절대 포함하지 않는다