#app/tests/test_repository.py

"""
2026-07-28
DB 쓰기 실패 rollback / 좋아요 중복 INSERT 처리 테스트
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.orm import User
from app.database.repository import LikeRepository, PostRepository, UserRepository


def _make_user() -> User:
    return User(
        email="test@example.com",
        password="hash",
        nickname="tester",
        is_verified=False,
        can_comment=True,
        can_write_post=False,
        can_upload=False,
        can_manage_category=False,
        can_manage_post=False,
        can_manage_user=False,
        suspended_until=None,
        is_banned=False,
        created_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )


def _mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.add = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_save_user_rolls_back_on_integrity_error():
    session = _mock_session()
    session.commit.side_effect = IntegrityError(
        "duplicate user",
        {},
        Exception("unique violation"),
    )
    repo = UserRepository(session=session)

    with pytest.raises(IntegrityError):
        await repo.save_user(_make_user())

    session.rollback.assert_awaited_once()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_like_add_uses_on_conflict_do_nothing():
    session = _mock_session()
    repo = LikeRepository(session=session)

    await repo.add(user_id=1, post_id=2)

    statement = session.execute.await_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "ON CONFLICT ON CONSTRAINT uq_likes_user_post DO NOTHING" in sql
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_posts_uses_aggregate_query_and_searches_all_fields():
    """목록은 페이지당 집계 쿼리 1회이며 제목·본문·작성자를 함께 검색한다."""
    session = _mock_session()
    result = Mock()
    result.all.return_value = []
    session.execute.return_value = result
    session.scalar.return_value = 0
    repo = PostRepository(session=session)

    rows, total = await repo.get_posts(
        order="desc",
        page=2,
        size=20,
        query="fastapi",
        category_id=3,
        user_id=None,
        include_deleted=False,
    )

    assert rows == []
    assert total == 0
    session.execute.assert_awaited_once()
    session.scalar.assert_awaited_once()

    statement = session.execute.await_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "comments" in sql
    assert "likes" in sql
    assert "posts.title" in sql
    assert "posts.contents" in sql
    assert "users.nickname" in sql
    assert "LIMIT 20 OFFSET 20" in sql