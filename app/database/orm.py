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
회원 등급 (role)
'''

from enum import StrEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from .connection import Base    # connection의 Base 재사용 (새로 만들지 않음)


class UserRole(StrEnum):
    # 값을 문자열로 저장한다. 정수로 두면 나중에 등급이 늘 때
    # 순서를 비집고 넣어야 하고, DB를 눈으로 볼 때도 뜻이 안 보인다
    ADMIN = "admin"      # 글 작성 / 분류 관리 / 등급 변경
    MEMBER = "member"    # 댓글만


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    title: Mapped[str]
    contents: Mapped[str]                              # 마크다운 원문
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), default=None)
    is_deleted: Mapped[bool] = mapped_column(default=False)

    # N:1 이라 joined 로딩이 적합 (글 하나당 작성자·분류 하나)
    user: Mapped["User"] = relationship(back_populates="posts", lazy="joined")
    category: Mapped["Category"] = relationship(back_populates="posts", lazy="joined")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post")

    def __repr__(self):
        return f"Post(id={self.id}, title={self.title})"

    @classmethod
    def create(cls, request, user_id: int) -> "Post":
        now = datetime.now(timezone.utc)
        return cls(
            title=request.title,
            contents=request.contents,
            user_id=user_id,          # 작성자는 요청이 아니라 토큰에서 온다
            category_id=request.category_id,
            created_at=now,
            updated_at=now,
        )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # 자기 테이블을 가리킨다. None 이면 원댓글, 값이 있으면 그 댓글의 답글.
    # 깊이 1 제한은 DB가 아니라 핸들러가 지킨다 (답글에 답글을 막는다)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id"), index=True, default=None
    )
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
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


class Upload(Base):    # 업로드된 파일 기록 (본문 위치는 마크다운이 갖는다)
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(256))
    content_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int]
    created_at: Mapped[datetime]

    def __repr__(self):
        return f"Upload(id={self.id}, filename={self.filename})"

    @classmethod
    def create(
        cls, user_id: int, filename: str, original_name: str,
        content_type: str, size: int,
    ) -> "Upload":
        return cls(
            user_id=user_id,
            filename=filename,
            original_name=original_name,
            content_type=content_type,
            size=size,
            created_at=datetime.now(timezone.utc),
        )


class User(Base):    # 회원 테이블
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(256))
    nickname: Mapped[str] = mapped_column(String(64), unique=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    role: Mapped[str] = mapped_column(String(16), default=UserRole.MEMBER)
    created_at: Mapped[datetime]

    posts: Mapped[list["Post"]] = relationship(back_populates="user")
    comments: Mapped[list["Comment"]] = relationship(back_populates="user")

    def __repr__(self):
        return f"User(id={self.id}, email={self.email}, role={self.role})"

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @classmethod
    def create(cls, email: str, hashed_password: str, nickname: str) -> "User":
        # 반드시 해싱된 비번을 받는다 (평문 저장 금지)
        # 가입은 언제나 최하위 등급. 올리는 건 관리자만 할 수 있다
        return cls(
            email=email,
            password=hashed_password,
            nickname=nickname,
            role=UserRole.MEMBER,
            created_at=datetime.now(timezone.utc),
        )


class Category(Base):    # 글 분류 (사이드바)
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # URL에 쓰는 이름
    name: Mapped[str] = mapped_column(String(32), unique=True)              # 화면에 보이는 이름
    display_order: Mapped[int] = mapped_column(default=0)

    posts: Mapped[list["Post"]] = relationship(back_populates="category")

    def __repr__(self):
        return f"Category(id={self.id}, slug={self.slug})"

    @classmethod
    def create(cls, request) -> "Category":
        return cls(
            slug=request.slug,
            name=request.name,
            display_order=request.display_order,
        )