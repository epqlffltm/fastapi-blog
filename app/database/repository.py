#app/database/repository.py

'''
2026-07-20
get 전체조회 api

2026-07-21
DB 접근 계층 (repository)
'''

from fastapi import Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .connection import get_db
from .orm import Post, Comment


class PostRepository:
    def __init__(self, session: Session = Depends(get_db)):
        self.session = session

    def get_posts(self, order: str) -> list[Post]:
        stmt = select(Post).where(Post.is_deleted == False)
        if order == "asc":
            stmt = stmt.order_by(Post.created_at.asc())
        elif order == "desc":
            stmt = stmt.order_by(Post.created_at.desc())
        else:
            stmt = stmt.order_by(func.random())
        return list(self.session.scalars(stmt).all())

    def get_post_by_id(self, id: int) -> Post | None:
        return self.session.scalar(
            select(Post).where(Post.id == id).where(Post.is_deleted == False)
        )

    def count_comments(self, post_id: int) -> int:
        return self.session.scalar(
            select(func.count(Comment.id))
            .where(Comment.post_id == post_id)
            .where(Comment.is_deleted == False)
        )

    def save(self, post: Post) -> Post:
        self.session.add(post)
        self.session.commit()
        self.session.refresh(post)
        return post

    def save_with_images(self, post: Post, image_urls: list[str]) -> Post:
        # 글 저장 → id 확보 → 이미지 매달기 → 커밋
        self.session.add(post)
        self.session.flush()   # commit 전에 post.id 받기
        for order, url in enumerate(image_urls):
            image = Image.create(url=url, post_id=post.id, display_order=order)
            self.session.add(image)
        self.session.commit()
        self.session.refresh(post)
        return post

    def update(self, post: Post) -> Post:
        # 이미 세션이 추적 중인 객체 → commit만
        self.session.commit()
        self.session.refresh(post)
        return post


class CommentRepository:
    def __init__(self, session: Session = Depends(get_db)):
        self.session = session

    def get_comment_by_id(self, id: int) -> Comment | None:
        return self.session.scalar(
            select(Comment).where(Comment.id == id).where(Comment.is_deleted == False)
        )

    def save(self, comment: Comment) -> Comment:
        self.session.add(comment)
        self.session.commit()
        self.session.refresh(comment)
        return comment

    def update(self, comment: Comment) -> Comment:
        self.session.commit()
        self.session.refresh(comment)
        return comment