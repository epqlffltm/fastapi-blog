#app/database/repository.py

'''
2026-07-20
get 전체조회 api

2026-07-21
DB 접근 계층 (repository)

2026-07-23
UserRepository 추가

2026-07-24
CategoryRepository 추가 / 목록에 분류 필터
UploadRepository 추가 (save_with_images 제거)
회원 목록 / 분류 저장

2026-07-25
분류 이름 변경 / 삭제(미분류로 재배치 후 삭제) / 글 수 카운트

2026-07-26
조회수 원자적 증가

2026-07-26
LikeRepository (좋아요 추가/삭제/카운트/존재확인)
'''

from fastapi import Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .connection import get_db
from .orm import Post, Comment, Upload, User, Category, Like


class PostRepository:
    def __init__(self, session: Session = Depends(get_db)):
        self.session = session

    def get_posts(
        self, order: str, category_id: int | None = None, include_deleted: bool = False
    ) -> list[Post]:
        stmt = select(Post)
        if not include_deleted:
            stmt = stmt.where(Post.is_deleted == False)
        if category_id is not None:
            stmt = stmt.where(Post.category_id == category_id)
        if order == "asc":
            stmt = stmt.order_by(Post.created_at.asc())
        elif order == "desc":
            stmt = stmt.order_by(Post.created_at.desc())
        else:
            stmt = stmt.order_by(func.random())
        return list(self.session.scalars(stmt).all())

    def get_post_by_id(self, id: int, include_deleted: bool = False) -> Post | None:
        stmt = select(Post).where(Post.id == id)
        if not include_deleted:
            stmt = stmt.where(Post.is_deleted == False)
        return self.session.scalar(stmt)

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

    def update(self, post: Post) -> Post:
        # 이미 세션이 추적 중인 객체 → commit만
        self.session.commit()
        self.session.refresh(post)
        return post

    def increment_view_count(self, post_id: int) -> int:
        # DB 레벨에서 원자적으로 +1 (읽고-더하고-쓰기 사이의 경합을 피한다).
        # 갱신 후의 값을 다시 읽어 응답에 쓴다
        self.session.query(Post).filter(Post.id == post_id).update(
            {Post.view_count: Post.view_count + 1}, synchronize_session=False
        )
        self.session.commit()
        return self.session.scalar(select(Post.view_count).where(Post.id == post_id))


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

    def get_users(self) -> list[User]:
        return list(self.session.scalars(select(User).order_by(User.id)).all())

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

    def get_category_by_name(self, name: str) -> Category | None:
        return self.session.scalar(select(Category).where(Category.name == name))

    def get_category_by_id(self, id: int) -> Category | None:
        return self.session.scalar(select(Category).where(Category.id == id))

    def count_posts(self, category_id: int) -> int:
        # 소프트삭제된 글도 category_id 로 FK 를 물고 있으므로 is_deleted 를 가리지 않는다
        return self.session.scalar(
            select(func.count(Post.id)).where(Post.category_id == category_id)
        )

    def save(self, category: Category) -> Category:
        self.session.add(category)
        self.session.commit()
        self.session.refresh(category)
        return category

    def update(self, category: Category) -> Category:
        # 이미 세션이 추적 중인 객체 → commit만
        self.session.commit()
        self.session.refresh(category)
        return category

    def reassign_and_delete(self, category: Category, fallback_id: int) -> None:
        # 그 분류의 글을 전부 미분류로 옮긴 뒤 빈 분류를 삭제한다.
        # 소프트삭제된 글도 category_id 로 FK 를 물고 있으므로 is_deleted 를 안 가린다.
        # 두 작업을 한 커밋으로 묶어 중간 실패 시 어정쩡한 상태를 남기지 않는다
        self.session.query(Post).filter(Post.category_id == category.id).update(
            {Post.category_id: fallback_id}, synchronize_session=False
        )
        self.session.delete(category)
        self.session.commit()


class UploadRepository:
    def __init__(self, session: Session = Depends(get_db)):
        self.session = session

    def save(self, upload: Upload) -> Upload:
        self.session.add(upload)
        self.session.commit()
        self.session.refresh(upload)
        return upload



class LikeRepository:
    def __init__(self, session: Session = Depends(get_db)):
        self.session = session

    def count_for_post(self, post_id: int) -> int:
        # 좋아요 수는 캐싱하지 않고 매번 센다 (이 규모에선 정확·단순이 이득)
        return self.session.scalar(
            select(func.count(Like.id)).where(Like.post_id == post_id)
        )

    def exists(self, user_id: int, post_id: int) -> bool:
        row = self.session.scalar(
            select(Like.id).where(
                Like.user_id == user_id, Like.post_id == post_id
            )
        )
        return row is not None

    def add(self, user_id: int, post_id: int) -> None:
        self.session.add(Like.create(user_id=user_id, post_id=post_id))
        self.session.commit()

    def remove(self, user_id: int, post_id: int) -> None:
        self.session.query(Like).filter(
            Like.user_id == user_id, Like.post_id == post_id
        ).delete(synchronize_session=False)
        self.session.commit()