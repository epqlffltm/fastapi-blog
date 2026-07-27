"""datetime columns to timestamptz

Revision ID: 8678755e0daa
Revises: 7ae6a4220e8c
Create Date: 2026-07-27 22:05:13.202947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8678755e0daa'
down_revision: Union[str, Sequence[str], None] = '7ae6a4220e8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 기존 값은 전부 UTC 로 저장돼 있었다(naive). timestamptz 로 바꿀 때
# "이 값들은 UTC 다" 라고 명시해야 서버 타임존으로 오해석되지 않는다.
def _to_tz(table: str, column: str, nullable: bool) -> None:
    op.alter_column(
        table, column,
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=nullable,
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )


def _to_naive(table: str, column: str, nullable: bool) -> None:
    op.alter_column(
        table, column,
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=nullable,
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )


def upgrade() -> None:
    """Upgrade schema."""
    _to_tz('comments', 'created_at', False)
    _to_tz('comments', 'updated_at', False)
    _to_tz('likes', 'created_at', False)
    _to_tz('posts', 'created_at', False)
    _to_tz('posts', 'updated_at', False)
    _to_tz('uploads', 'created_at', False)
    _to_tz('users', 'created_at', False)
    _to_tz('users', 'suspended_until', True)


def downgrade() -> None:
    """Downgrade schema."""
    _to_naive('users', 'suspended_until', True)
    _to_naive('users', 'created_at', False)
    _to_naive('uploads', 'created_at', False)
    _to_naive('posts', 'updated_at', False)
    _to_naive('posts', 'created_at', False)
    _to_naive('likes', 'created_at', False)
    _to_naive('comments', 'updated_at', False)
    _to_naive('comments', 'created_at', False)