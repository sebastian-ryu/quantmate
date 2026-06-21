"""재무비율 현금흐름과 배당 지표 확장

Revision ID: 0011_fund_cash_div
Revises: 0010_extend_fundamental_ratios
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011_fund_cash_div"
down_revision = "0010_extend_fundamental_ratios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _add_column_if_missing("free_cash_flow", sa.Column("free_cash_flow", sa.Numeric(24, 4), nullable=True))
    _add_column_if_missing("dividends_paid", sa.Column("dividends_paid", sa.Numeric(24, 4), nullable=True))
    _add_column_if_missing(
        "cash_and_cash_equivalents",
        sa.Column("cash_and_cash_equivalents", sa.Numeric(24, 4), nullable=True),
    )
    _add_column_if_missing("ebitda", sa.Column("ebitda", sa.Numeric(24, 4), nullable=True))
    _add_column_if_missing("fcf_yield", sa.Column("fcf_yield", sa.Numeric(12, 4), nullable=True))
    _add_column_if_missing("ev_ebitda", sa.Column("ev_ebitda", sa.Numeric(12, 4), nullable=True))
    _add_column_if_missing("dividend_yield", sa.Column("dividend_yield", sa.Numeric(12, 4), nullable=True))
    _add_column_if_missing("payout_ratio", sa.Column("payout_ratio", sa.Numeric(12, 4), nullable=True))
    _add_column_if_missing("dividend_growth", sa.Column("dividend_growth", sa.Numeric(12, 4), nullable=True))
    _add_column_if_missing("dividend_streak_years", sa.Column("dividend_streak_years", sa.Integer(), nullable=True))
    _add_column_if_missing(
        "dividend_stability_score",
        sa.Column("dividend_stability_score", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    for column_name in (
        "dividend_stability_score",
        "dividend_streak_years",
        "dividend_growth",
        "payout_ratio",
        "dividend_yield",
        "ev_ebitda",
        "fcf_yield",
        "ebitda",
        "cash_and_cash_equivalents",
        "dividends_paid",
        "free_cash_flow",
    ):
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
