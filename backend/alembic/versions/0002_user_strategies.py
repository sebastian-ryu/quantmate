"""사용자 등록 전략 테이블

Revision ID: 0002_user_strategies
Revises: 0001_initial_market_data
Create Date: 2026-06-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_user_strategies"
down_revision = "0001_initial_market_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_strategies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_user_strategies_code"),
    )
    op.create_index("ix_user_strategies_code", "user_strategies", ["code"])


def downgrade() -> None:
    op.drop_index("ix_user_strategies_code", table_name="user_strategies")
    op.drop_table("user_strategies")
