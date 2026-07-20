#app/database/orm.py

'''
2026-07-20
orm 모델링 (posts, comments, images)
get 전체조회 api
'''

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
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


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    url: Mapped[str]
    display_order: Mapped[int] = mapped_column(default=0)

    post: Mapped["Post"] = relationship(back_populates="images")

    def __repr__(self):
        return f"Image(id={self.id}, post_id={self.post_id}, url={self.url})"