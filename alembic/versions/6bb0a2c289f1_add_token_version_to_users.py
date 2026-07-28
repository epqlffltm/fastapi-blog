"""add token_version to users

Revision ID: 6bb0a2c289f1
Revises: 8678755e0daa
Create Date: 2026-07-28 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6bb0a2c289f1"
down_revision: Union[str, Sequence[str], None] = "8678755e0daa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """기존 계정은 버전 0으로 채운 뒤 애플리케이션 기본값에 맡긴다."""
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.alter_column(
        "users",
        "token_version",
        existing_type=sa.Integer(),
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
