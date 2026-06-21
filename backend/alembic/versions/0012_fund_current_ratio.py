"""재무비율 유동비율 지표 확장

Revision ID: 0012_fund_current
Revises: 0011_fund_cash_div
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012_fund_current"
down_revision = "0011_fund_cash_div"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _add_column_if_missing("current_assets", sa.Column("current_assets", sa.Numeric(24, 4), nullable=True))
    _add_column_if_missing("current_liabilities", sa.Column("current_liabilities", sa.Numeric(24, 4), nullable=True))
    _add_column_if_missing("current_ratio", sa.Column("current_ratio", sa.Numeric(12, 4), nullable=True))


def downgrade() -> None:
    for column_name in ("current_ratio", "current_liabilities", "current_assets"):
        _drop_column_if_exists(column_name)


def _column_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("fundamental_ratios")}


def _add_column_if_missing(column_name: str, column: sa.Column) -> None:
    if column_name not in _column_names():
        op.add_column("fundamental_ratios", column)


def _drop_column_if_exists(column_name: str) -> None:
    if column_name in _column_names():
        op.drop_column("fundamental_ratios", column_name)
