"""공개 프로필에 노출할 댓글을 안전하게 조회한다."""

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from .connection import get_db
from .orm import Comment, Post


class ProfileCommentRepository:
    """댓글 자체와 소속 글의 삭제 상태를 함께 적용하는 조회 전용 저장소."""

    def __init__(self, session: AsyncSession = Depends(get_db)):
        self.session = session

    async def get_comments_by_user(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20,
        include_deleted: bool = False,
    ) -> tuple[list[tuple[Comment, Post]], int]:
        filters = [Comment.user_id == user_id]
        if not include_deleted:
            filters.extend(
                (
                    Comment.is_deleted.is_(False),
                    Post.is_deleted.is_(False),
                )
            )

        base = (
            select(Comment, Post)
            .join(Post, Post.id == Comment.post_id)
            .where(*filters)
        )

        total = await self.session.scalar(
            select(func.count(Comment.id))
            .join(Post, Post.id == Comment.post_id)
            .where(*filters)
        )

        result = await self.session.execute(
            base.order_by(Comment.created_at.desc(), Comment.id.desc())
            .offset((page - 1) * size)
            .limit(size)
            .options(noload(Comment.user))
        )
        return [(row[0], row[1]) for row in result.all()], int(total or 0)
