#app/schema/response.py

'''
2026-07-20
orm → http response 스키마
get 단일 조회 api

2026-07-23
회원 응답 추가
토큰 응답 추가
작성자를 user 관계에서 가져오도록 변경
'''

from pydantic import BaseModel, ConfigDict
from datetime import datetime


# 작성자 요약 (닉네임 표시용)
class UserBriefSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str


# 목록의 글 하나 (댓글 수 포함)
class PostListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    user: UserBriefSchema
    created_at: datetime
    comment_count: int


# 목록 전체
class ListPostSchema(BaseModel):
    posts: list[PostListItemSchema]


# 댓글 하나
class CommentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user: UserBriefSchema
    contents: str
    created_at: datetime


# 이미지 하나
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
    user: UserBriefSchema
    contents: str
    created_at: datetime
    updated_at: datetime
    comments: list[CommentSchema]
    images: list[ImageSchema]


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nickname: str
    is_verified: bool

'''
class JWTResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
'''