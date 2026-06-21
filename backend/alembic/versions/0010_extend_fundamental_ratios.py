"""재무비율 수익성 지표 확장

Revision ID: 0010_extend_fundamental_ratios
Revises: 0009_strategy_selection_runs
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_extend_fundamental_ratios"
down_revision = "0009_strategy_selection_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fundamental_ratios", sa.Column("roa", sa.Numeric(12, 4), nullable=True))
    op.add_column("fundamental_ratios", sa.Column("operating_margin", sa.Numeric(12, 4), nullable=True))
    op.add_column("fundamental_ratios", sa.Column("net_margin", sa.Numeric(12, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("fundamental_ratios", "net_margin")
    op.drop_column("fundamental_ratios", "operating_margin")
    op.drop_column("fundamental_ratios", "roa")
