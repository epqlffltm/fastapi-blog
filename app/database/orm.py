#app/database/orm.py

'''
2026-07-20
orm 모델링 (posts, comments, images)
get 전체조회 api

2026-07-21
create classmethod 추가 (post api)

2026-07-23
회원 테이블
'''

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from .connection import Base    # connection의 Base 재사용 (새로 만들지 않음)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    title: Mapped[str]
    nickname: Mapped[str]
    contents: Mapped[str]
    is_deleted: Mapped[bool] = mapped_column(default=False)

    comments: Mapped[list["Comment"]] = relationship(back_populates="post")
    images: Mapped[list["Image"]] = relationship(back_populates="post")

    def __repr__(self):
        return f"Post(id={self.id}, title={self.title})"

    @classmethod
    def create(cls, request) -> "Post":
        now = datetime.now(timezone.utc)
        return cls(
            title=request.title,
            nickname=request.nickname,
            contents=request.contents,
            created_at=now,
            updated_at=now,
        )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    nickname: Mapped[str]
    contents: Mapped[str]
    is_deleted: Mapped[bool] = mapped_column(default=False)

    post: Mapped["Post"] = relationship(back_populates="comments")

    def __repr__(self):
        return f"Comment(id={self.id}, post_id={self.post_id})"

    @classmethod
    def create(cls, request, post_id: int) -> "Comment":
        now = datetime.now(timezone.utc)
        return cls(
            post_id=post_id,
            nickname=request.nickname,
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
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)   # 로그인 ID
    password: Mapped[str] = mapped_column(String(256))                          # bcrypt 해시
    nickname: Mapped[str] = mapped_column(String(64), unique=True)              # 표시 이름
    is_verified: Mapped[bool] = mapped_column(default=False)                    # 이메일 인증 여부
    created_at: Mapped[datetime]

    # posts/comments relationship은 Post/Comment에 user_id FK 추가한 뒤에

    def __repr__(self):
        return f"User(id={self.id}, email={self.email})"

    @classmethod
    def create(cls, email: str, hashed_password: str, nickname: str) -> "User":
        # 반드시 해싱된 비번을 받는다 (평문 저장 금지)
        return cls(
            email=email,
            password=hashed_password,
            nickname=nickname,
            created_at=datetime.now(timezone.utc),
        )