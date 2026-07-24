#app/schema/response.py

'''
2026-07-20
orm → http response 스키마
get 단일 조회 api

2026-07-23
회원 응답 추가
작성자를 user 관계에서 가져오도록 변경

2026-07-24
분류 스키마 추가
'''

from pydantic import BaseModel, ConfigDict
from datetime import datetime


# 작성자 요약 (닉네임 표시용)
class UserBriefSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str


# 분류 (글에 딸려 나가는 형태) — 아래에서 참조하므로 먼저 정의한다
class CategorySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str


# 사이드바용 (글 개수는 Category 에 없는 값이라 핸들러가 직접 채운다)
class CategoryListItemSchema(BaseModel):
    id: int
    slug: str
    name: str
    post_count: int


class ListCategorySchema(BaseModel):
    categories: list[CategoryListItemSchema]


# 목록의 글 하나 (댓글 수 포함)
class PostListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    user: UserBriefSchema
    category: CategorySchema
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
    category: CategorySchema
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
    # password 는 절대 포함하지 않는다