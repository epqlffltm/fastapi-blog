#app/database/repository.py

'''
2026-07-20
get 전체조회 api

2026-07-21
DB 접근 계층 (repository)

2026-07-23
UserRepository 추가
UserRepository에 메서드 추가

2026-07-24
CategoryRepository 추가 / 목록에 분류 필터
'''

from fastapi import Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .connection import get_db
from .orm import Post, Comment, Image, User, Category


class PostRepository:
    def __init__(self, session: Session = Depends(get_db)):
        self.session = session

    def get_posts(self, order: str, category_id: int | None = None) -> list[Post]:
        stmt = select(Post).where(Post.is_deleted == False)
        if category_id is not None:
            stmt = stmt.where(Post.category_id == category_id)
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


class UserRepository:
    def __init__(self, session: Session = Depends(get_db)):
        self.session = session

    def get_user_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def get_user_by_nickname(self, nickname: str) -> User | None:
        return self.session.scalar(select(User).where(User.nickname == nickname))

    def get_user_by_id(self, id: int) -> User | None:
        return self.session.scalar(select(User).where(User.id == id))

    def save_user(self, user: User) -> User:
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def update_user(self, user: User) -> User:
        self.session.commit()
        self.session.refresh(user)
        return user


class CategoryRepository:
    def __init__(self, session: Session = Depends(get_db)):
        self.session = session

    def get_categories_with_counts(self) -> list[tuple[Category, int]]:
        # GROUP BY 로 분류별 글 수를 한 방에 센다 (분류마다 COUNT 를 날리지 않는다)
        # outerjoin 이라 글이 하나도 없는 분류도 목록에 남는다
        stmt = (
            select(Category, func.count(Post.id))
            .outerjoin(
                Post,
                (Post.category_id == Category.id) & (Post.is_deleted == False),
            )
            .group_by(Category.id)
            .order_by(Category.display_order, Category.id)
        )
        return [(row[0], row[1]) for row in self.session.execute(stmt).all()]

    def get_category_by_slug(self, slug: str) -> Category | None:
        return self.session.scalar(select(Category).where(Category.slug == slug))

    def get_category_by_id(self, id: int) -> Category | None:
        return self.session.scalar(select(Category).where(Category.id == id))