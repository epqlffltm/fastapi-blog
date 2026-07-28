#app/database/orm.py

'''
2026-07-20
orm 모델링 (posts, comments, images)
get 전체조회 api

2026-07-21
create classmethod 추가 (post api)

2026-07-23
회원 테이블
nickname → user_id FK 전환

2026-07-24
분류(categories) 테이블 추가
images → uploads (업로드 파일 기록) 전환, 본문 썸네일
대댓글 (parent_id 자기참조 FK, 1단계)
role → 권한 체크박스 / 정지 · 강퇴

2026-07-26
조회수 컬럼 / 좋아요(likes) 테이블

2026-07-28
비밀번호 변경 시 기존 JWT를 무효화하는 token_version 추가
'''

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .connection import Base


PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("can_comment", "댓글"),
    ("can_write_post", "글쓰기"),
    ("can_upload", "이미지 업로드"),
    ("can_manage_category", "분류 관리"),
    ("can_manage_post", "글 관리"),
    ("can_manage_user", "회원 관리"),
)
PERMISSION_NAMES: tuple[str, ...] = tuple(name for name, _ in PERMISSIONS)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    title: Mapped[str]
    contents: Mapped[str]
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), default=None)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    view_count: Mapped[int] = mapped_column(default=0)

    user: Mapped["User"] = relationship(back_populates="posts", lazy="joined")
    category: Mapped["Category"] = relationship(back_populates="posts", lazy="joined")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post", lazy="selectin")

    def __repr__(self):
        return f"Post(id={self.id}, title={self.title})"

    @classmethod
    def create(cls, request, user_id: int) -> "Post":
        now = datetime.now(timezone.utc)
        return cls(
            title=request.title,
            contents=request.contents,
            user_id=user_id,
            category_id=request.category_id,
            created_at=now,
            updated_at=now,
        )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id"), index=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    contents: Mapped[str]
    is_deleted: Mapped[bool] = mapped_column(default=False)

    post: Mapped["Post"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship(back_populates="comments", lazy="joined")

    def __repr__(self):
        return f"Comment(id={self.id}, post_id={self.post_id}, parent_id={self.parent_id})"

    @classmethod
    def create(cls, request, post_id: int, user_id: int) -> "Comment":
        now = datetime.now(timezone.utc)
        return cls(
            post_id=post_id,
            user_id=user_id,
            parent_id=request.parent_id,
            contents=request.contents,
            created_at=now,
            updated_at=now,
        )


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(256))
    content_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self):
        return f"Upload(id={self.id}, filename={self.filename})"

    @classmethod
    def create(
        cls,
        user_id: int,
        filename: str,
        original_name: str,
        content_type: str,
        size: int,
    ) -> "Upload":
        return cls(
            user_id=user_id,
            filename=filename,
            original_name=original_name,
            content_type=content_type,
            size=size,
            created_at=datetime.now(timezone.utc),
        )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(256))
    token_version: Mapped[int] = mapped_column(default=0)
    nickname: Mapped[str] = mapped_column(String(64), unique=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bio: Mapped[str | None] = mapped_column(String(500), default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(255), default=None)

    can_comment: Mapped[bool] = mapped_column(default=True)
    can_write_post: Mapped[bool] = mapped_column(default=False)
    can_upload: Mapped[bool] = mapped_column(default=False)
    can_manage_category: Mapped[bool] = mapped_column(default=False)
    can_manage_user: Mapped[bool] = mapped_column(default=False)
    can_manage_post: Mapped[bool] = mapped_column(default=False)

    suspended_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    is_banned: Mapped[bool] = mapped_column(default=False)

    posts: Mapped[list["Post"]] = relationship(back_populates="user", lazy="raise")
    comments: Mapped[list["Comment"]] = relationship(back_populates="user", lazy="raise")

    def __repr__(self):
        return f"User(id={self.id}, email={self.email})"

    @property
    def is_suspended(self) -> bool:
        if self.suspended_until is None:
            return False
        return self.suspended_until > datetime.now(timezone.utc)

    @property
    def is_active(self) -> bool:
        return not self.is_banned and not self.is_suspended

    def grant_all(self) -> None:
        for name in PERMISSION_NAMES:
            setattr(self, name, True)

    def revoke_all(self) -> None:
        for name in PERMISSION_NAMES:
            setattr(self, name, False)

    @classmethod
    def create(cls, email: str, hashed_password: str, nickname: str) -> "User":
        return cls(
            email=email,
            password=hashed_password,
            token_version=0,
            nickname=nickname,
            can_comment=True,
            can_write_post=False,
            can_upload=False,
            can_manage_category=False,
            can_manage_post=False,
            can_manage_user=False,
            suspended_until=None,
            is_banned=False,
            created_at=datetime.now(timezone.utc),
        )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    display_order: Mapped[int] = mapped_column(default=0)

    posts: Mapped[list["Post"]] = relationship(back_populates="category", lazy="raise")

    def __repr__(self):
        return f"Category(id={self.id}, slug={self.slug})"

    @classmethod
    def create(cls, request) -> "Category":
        return cls(
            slug=request.slug,
            name=request.name,
            display_order=request.display_order,
        )


class Like(Base):
    __tablename__ = "likes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_likes_user_post"),
    )

    def __repr__(self):
        return f"Like(user_id={self.user_id}, post_id={self.post_id})"

    @classmethod
    def create(cls, user_id: int, post_id: int) -> "Like":
        return cls(
            user_id=user_id,
            post_id=post_id,
            created_at=datetime.now(timezone.utc),
        )
