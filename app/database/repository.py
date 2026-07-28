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

2026-07-28
쓰기 작업 실패 시 rollback / 좋아요 중복 INSERT 원자 처리

2026-07-28
게시글 목록 페이지네이션 / 검색 / 댓글·좋아요 집계

2026-07-28
유저별 댓글 목록 조회 추가
'''

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy import select, func, or_, update as sa_update, delete as sa_delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload
from .connection import get_db
from .orm import Post, Comment, Upload, User, Category, Like


@asynccontextmanager
async def _write_transaction(session: AsyncSession):
    """쓰기 중 실패하면 세션을 rollback한 뒤 원래 예외를 다시 전달한다."""
    try:
        yield
        await session.commit()
    except Exception:
        await session.rollback()
        raise


class PostRepository:
    def __init__(self, session: AsyncSession = Depends(get_db)):
        self.session = session

    async def get_posts(
        self,
        order: str,
        page: int,
        size: int,
        query: str | None = None,
        category_id: int | None = None,
        user_id: int | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[tuple[Post, int, int]], int]:
        """페이지 글과 댓글·좋아요 수를 함께 조회하고 전체 결과 수를 반환한다."""
        comment_counts = (
            select(
                Comment.post_id.label("post_id"),
                func.count(Comment.id).label("comment_count"),
            )
            .where(Comment.is_deleted.is_(False))
            .group_by(Comment.post_id)
            .subquery()
        )
        like_counts = (
            select(
                Like.post_id.label("post_id"),
                func.count(Like.id).label("like_count"),
            )
            .group_by(Like.post_id)
            .subquery()
        )

        filters = []
        if not include_deleted:
            filters.append(Post.is_deleted.is_(False))
        if category_id is not None:
            filters.append(Post.category_id == category_id)
        if user_id is not None:
            filters.append(Post.user_id == user_id)
        if query:
            # %, _가 검색 와일드카드로 해석되지 않고 문자 그대로 검색되게 한다.
            escaped = (
                query.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            pattern = f"%{escaped}%"
            filters.append(
                or_(
                    Post.title.ilike(pattern, escape="\\"),
                    Post.contents.ilike(pattern, escape="\\"),
                    Post.user.has(
                        User.nickname.ilike(pattern, escape="\\")
                    ),
                )
            )

        total = await self.session.scalar(
            select(func.count(Post.id)).where(*filters)
        )

        stmt = (
            select(
                Post,
                func.coalesce(comment_counts.c.comment_count, 0).label(
                    "comment_count"
                ),
                func.coalesce(like_counts.c.like_count, 0).label("like_count"),
            )
            .outerjoin(
                comment_counts,
                comment_counts.c.post_id == Post.id,
            )
            .outerjoin(
                like_counts,
                like_counts.c.post_id == Post.id,
            )
            .where(*filters)
            # 목록에는 댓글 본문이 필요 없다 (수는 위 서브쿼리로 이미 셌다).
            # 막지 않으면 Post.comments 의 selectin 이 20개 글의 댓글을 통째로 더 읽는다
            .options(noload(Post.comments))
        )

        if order == "asc":
            stmt = stmt.order_by(Post.created_at.asc(), Post.id.asc())
        elif order == "random":
            stmt = stmt.order_by(func.random())
        else:
            stmt = stmt.order_by(Post.created_at.desc(), Post.id.desc())

        stmt = stmt.offset((page - 1) * size).limit(size)
        result = await self.session.execute(stmt)

        rows = [
            (row[0], int(row[1]), int(row[2]))
            for row in result.all()
        ]
        return rows, int(total or 0)

    async def get_post_by_id(
        self, id: int, include_deleted: bool = False, fresh: bool = False
    ) -> Post | None:
        stmt = select(Post).where(Post.id == id)
        if not include_deleted:
            stmt = stmt.where(Post.is_deleted == False)
        if fresh:
            # 세션 캐시(identity map)를 무시하고 DB 에서 다시 읽는다.
            # 댓글을 방금 저장한 뒤처럼, 관계(comments)를 최신으로 다시 로드해야 할 때
            stmt = stmt.execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def count_comments(self, post_id: int) -> int:
        return await self.session.scalar(
            select(func.count(Comment.id))
            .where(Comment.post_id == post_id)
            .where(Comment.is_deleted == False)
        )

    async def save(self, post: Post) -> Post:
        async with _write_transaction(self.session):
            self.session.add(post)
        await self.session.refresh(post)
        return post

    async def update(self, post: Post) -> Post:
        # 이미 세션이 추적 중인 객체 → commit만
        async with _write_transaction(self.session):
            pass
        await self.session.refresh(post)
        return post

    async def increment_view_count(self, post_id: int) -> int:
        # DB 레벨에서 원자적으로 +1 (읽고-더하고-쓰기 사이의 경합을 피한다).
        # 갱신 후의 값을 다시 읽어 응답에 쓴다
        async with _write_transaction(self.session):
            await self.session.execute(
                sa_update(Post)
                .where(Post.id == post_id)
                .values(view_count=Post.view_count + 1)
            )
        return await self.session.scalar(select(Post.view_count).where(Post.id == post_id))


class CommentRepository:
    def __init__(self, session: AsyncSession = Depends(get_db)):
        self.session = session

    async def get_comment_by_id(self, id: int) -> Comment | None:
        return await self.session.scalar(
            select(Comment).where(Comment.id == id).where(Comment.is_deleted == False)
        )

    async def save(self, comment: Comment) -> Comment:
        async with _write_transaction(self.session):
            self.session.add(comment)
        await self.session.refresh(comment)
        return comment

    async def update(self, comment: Comment) -> Comment:
        async with _write_transaction(self.session):
            pass
        await self.session.refresh(comment)
        return comment

    async def get_comments_by_user(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20,
        include_deleted: bool = False,
    ) -> tuple[list[tuple], int]:
        """
        유저가 작성한 댓글 + 소속 글 정보
        반환: ([(Comment, Post), ...], total)
        """
        filters = [Comment.user_id == user_id]
        if not include_deleted:
            filters.append(Comment.is_deleted.is_(False))

        total = await self.session.scalar(
            select(func.count(Comment.id)).where(*filters)
        )

        stmt = (
            select(Comment, Post)
            .join(Post, Post.id == Comment.post_id)
            .where(*filters)
            .order_by(Comment.created_at.desc(), Comment.id.desc())
            .offset((page - 1) * size)
            .limit(size)
            .options(noload(Comment.user))
        )

        result = await self.session.execute(stmt)
        rows = [(row[0], row[1]) for row in result.all()]
        return rows, int(total or 0)


class UserRepository:
    def __init__(self, session: AsyncSession = Depends(get_db)):
        self.session = session

    async def get_users(self) -> list[User]:
        result = await self.session.scalars(select(User).order_by(User.id))
        return list(result.all())

    async def get_user_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def get_user_by_nickname(self, nickname: str) -> User | None:
        return await self.session.scalar(select(User).where(User.nickname == nickname))

    async def get_user_by_id(self, id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.id == id))

    async def save_user(self, user: User) -> User:
        async with _write_transaction(self.session):
            self.session.add(user)
        await self.session.refresh(user)
        return user

    async def update_user(self, user: User) -> User:
        async with _write_transaction(self.session):
            pass
        await self.session.refresh(user)
        return user


class CategoryRepository:
    def __init__(self, session: AsyncSession = Depends(get_db)):
        self.session = session

    async def get_categories_with_counts(self) -> list[tuple[Category, int]]:
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
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_category_by_slug(self, slug: str) -> Category | None:
        return await self.session.scalar(select(Category).where(Category.slug == slug))

    async def get_category_by_name(self, name: str) -> Category | None:
        return await self.session.scalar(select(Category).where(Category.name == name))

    async def get_category_by_id(self, id: int) -> Category | None:
        return await self.session.scalar(select(Category).where(Category.id == id))

    async def count_posts(self, category_id: int) -> int:
        # 소프트삭제된 글도 category_id 로 FK 를 물고 있으므로 is_deleted 를 가리지 않는다
        return await self.session.scalar(
            select(func.count(Post.id)).where(Post.category_id == category_id)
        )

    async def save(self, category: Category) -> Category:
        async with _write_transaction(self.session):
            self.session.add(category)
        await self.session.refresh(category)
        return category

    async def update(self, category: Category) -> Category:
        # 이미 세션이 추적 중인 객체 → commit만
        async with _write_transaction(self.session):
            pass
        await self.session.refresh(category)
        return category

    async def reassign_and_delete(self, category: Category, fallback_id: int) -> None:
        # 그 분류의 글을 전부 미분류로 옮긴 뒤 빈 분류를 삭제한다.
        # 소프트삭제된 글도 category_id 로 FK 를 물고 있으므로 is_deleted 를 안 가린다.
        # 두 작업을 한 커밋으로 묶어 중간 실패 시 어정쩡한 상태를 남기지 않는다
        async with _write_transaction(self.session):
            await self.session.execute(
                sa_update(Post)
                .where(Post.category_id == category.id)
                .values(category_id=fallback_id)
            )
            await self.session.delete(category)


class UploadRepository:
    def __init__(self, session: AsyncSession = Depends(get_db)):
        self.session = session

    async def save(self, upload: Upload) -> Upload:
        async with _write_transaction(self.session):
            self.session.add(upload)
        await self.session.refresh(upload)
        return upload


class LikeRepository:
    def __init__(self, session: AsyncSession = Depends(get_db)):
        self.session = session

    async def count_for_post(self, post_id: int) -> int:
        # 좋아요 수는 캐싱하지 않고 매번 센다 (이 규모에선 정확·단순이 이득)
        return await self.session.scalar(
            select(func.count(Like.id)).where(Like.post_id == post_id)
        )

    async def exists(self, user_id: int, post_id: int) -> bool:
        row = await self.session.scalar(
            select(Like.id).where(
                Like.user_id == user_id, Like.post_id == post_id
            )
        )
        return row is not None

    async def add(self, user_id: int, post_id: int) -> None:
        # exists() 이후 다른 요청이 먼저 추가해도 unique 예외가 나지 않게 한다.
        stmt = (
            pg_insert(Like)
            .values(
                user_id=user_id,
                post_id=post_id,
                created_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_nothing(constraint="uq_likes_user_post")
        )
        async with _write_transaction(self.session):
            await self.session.execute(stmt)

    async def remove(self, user_id: int, post_id: int) -> None:
        async with _write_transaction(self.session):
            await self.session.execute(
                sa_delete(Like).where(
                    Like.user_id == user_id,
                    Like.post_id == post_id,
                )
            )