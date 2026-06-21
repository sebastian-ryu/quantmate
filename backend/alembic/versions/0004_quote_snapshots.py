"""KIS 현재가 스냅샷 테이블

Revision ID: 0004_quote_snapshots
Revises: 0003_backtest_runs
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_quote_snapshots"
down_revision = "0003_backtest_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quote_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=True),
        sa.Column("change_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("trading_value", sa.Numeric(24, 4), nullable=True),
        sa.Column("market_cap", sa.Numeric(24, 4), nullable=True),
        sa.Column("per", sa.Numeric(12, 4), nullable=True),
        sa.Column("pbr", sa.Numeric(12, 4), nullable=True),
        sa.Column("eps", sa.Numeric(18, 4), nullable=True),
        sa.Column("bps", sa.Numeric(18, 4), nullable=True),
        sa.Column("turnover_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("foreign_holding_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("foreign_net_buy_qty", sa.BigInteger(), nullable=True),
        sa.Column("program_net_buy_qty", sa.BigInteger(), nullable=True),
        sa.Column("high_52w", sa.Numeric(18, 4), nullable=True),
        sa.Column("low_52w", sa.Numeric(18, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_quote_snapshots_instrument_id",
        ),
        sa.UniqueConstraint(
            "instrument_id",
            "snapshot_date",
            "provider",
            name="uq_quote_snapshots_identity",
        ),
    )
    op.create_index("ix_quote_snapshots_snapshot_date", "quote_snapshots", ["snapshot_date"])
    op.create_index(
        "ix_quote_snapshots_instrument_date",
        "quote_snapshots",
        ["instrument_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_quote_snapshots_instrument_date", table_name="quote_snapshots")
    op.drop_index("ix_quote_snapshots_snapshot_date", table_name="quote_snapshots")
    op.drop_table("quote_snapshots")
