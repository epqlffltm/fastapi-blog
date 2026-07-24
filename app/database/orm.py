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
사이드 바 추가
'''

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from .connection import Base    # connection의 Base 재사용 (새로 만들지 않음)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    title: Mapped[str]
    contents: Mapped[str]
    is_deleted: Mapped[bool] = mapped_column(default=False)

    # N:1 이라 joined 로딩이 적합 (글 하나당 작성자·분류 하나)
    user: Mapped["User"] = relationship(back_populates="posts", lazy="joined")
    category: Mapped["Category"] = relationship(back_populates="posts", lazy="joined")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post")
    images: Mapped[list["Image"]] = relationship(back_populates="post")

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
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    contents: Mapped[str]
    is_deleted: Mapped[bool] = mapped_column(default=False)

    post: Mapped["Post"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship(back_populates="comments", lazy="joined")

    def __repr__(self):
        return f"Comment(id={self.id}, post_id={self.post_id})"

    @classmethod
    def create(cls, request, post_id: int, user_id: int) -> "Comment":
        now = datetime.now(timezone.utc)
        return cls(
            post_id=post_id,
            user_id=user_id,
            contents=request.contents,
            created_at=now,
            updated_at=now,
        )


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    url: Mapped[str]
    display_order: Mapped[int] = mapped_column(default=0)

    post: Mapped["Post"] = relationship(back_populates="images")

    def __repr__(self):
        return f"Image(id={self.id}, post_id={self.post_id}, url={self.url})"

    @classmethod
    def create(cls, url: str, post_id: int, display_order: int = 0) -> "Image":
        return cls(
            url=url,
            post_id=post_id,
            display_order=display_order,
        )


class User(Base):    # 회원 테이블
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(256))
    nickname: Mapped[str] = mapped_column(String(64), unique=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime]

    posts: Mapped[list["Post"]] = relationship(back_populates="user")
    comments: Mapped[list["Comment"]] = relationship(back_populates="user")

    def __repr__(self):
        return f"User(id={self.id}, email={self.email})"

    @classmethod
    def create(cls, email: str, hashed_password: str, nickname: str) -> "User":
        return cls(
            email=email,
            password=hashed_password,
            nickname=nickname,
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