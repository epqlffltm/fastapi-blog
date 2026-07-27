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
이미지 스키마 제거 / 목록에 썸네일 추가
대댓글 (parent_id) 및 삭제 자리표시자
권한 · 제재
'''

from pydantic import BaseModel, ConfigDict, model_validator
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
    thumbnail_url: str | None
    created_at: datetime
    comment_count: int
    is_deleted: bool
    view_count: int
    like_count: int


# 목록 전체
class ListPostSchema(BaseModel):
    posts: list[PostListItemSchema]


# 댓글 하나
class CommentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None
    user: UserBriefSchema | None
    contents: str
    is_deleted: bool
    created_at: datetime

    @model_validator(mode="after")
    def hide_deleted(self):
        # 자리표시자로 남은 댓글의 내용과 작성자는 내보내지 않는다.
        # 핸들러가 아니라 스키마가 막아야 어느 경로로 만들어도 새지 않는다
        if self.is_deleted:
            self.user = None
            self.contents = ""
        return self


# 글 상세 (본문은 마크다운, 이미지는 그 안에 있다)
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
    is_deleted: bool
    view_count: int


# 좋아요 토글 / 상태 조회 응답
class LikeResultSchema(BaseModel):
    like_count: int
    liked: bool          # 지금 보는 사람이 눌렀는지


# 남의 프로필용 — 공개해도 되는 정보만 (이메일·권한·제재상태는 절대 안 담는다)
class PublicUserSchema(BaseModel):
    id: int
    nickname: str
    bio: str | None
    avatar_url: str | None

    model_config = ConfigDict(from_attributes=True)


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nickname: str
    bio: str | None
    avatar_url: str | None
    is_verified: bool

    can_comment: bool
    can_write_post: bool
    can_upload: bool
    can_manage_category: bool
    can_manage_user: bool
    can_manage_post: bool

    suspended_until: datetime | None
    is_banned: bool
    is_suspended: bool      # 모델의 property. 기한이 지났는지까지 계산돼 나온다
    # password 는 절대 포함하지 않는다


# 관리 화면용 회원 목록
class ListUserSchema(BaseModel):
    users: list[UserSchema]


class UploadSchema(BaseModel):
    url: str
    filename: str
    size: int