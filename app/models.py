#app/models.py

'''
2026-07-20
SQLAlchemy 모델 정의 (posts, comments, images)
'''

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from .database import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    title: Mapped[str]
    nickname: Mapped[str]
    contents: Mapped[str]
    is_deleted: Mapped[bool] = mapped_column(default=False)

    comments: Mapped[list["Comment"]] = relationship(back_populates="post")
    images: Mapped[list["Image"]] = relationship(back_populates="post")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    nickname: Mapped[str]
    contents: Mapped[str]
    is_deleted: Mapped[bool] = mapped_column(default=False)

    post: Mapped["Post"] = relationship(back_populates="comments")


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    url: Mapped[str]
    display_order: Mapped[int] = mapped_column(default=0)

    post: Mapped["Post"] = relationship(back_populates="images")