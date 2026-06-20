"""초기 시장 데이터 테이블

Revision ID: 0001_initial_market_data
Revises:
Create Date: 2026-06-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_market_data"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "markets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("timezone", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_markets_code"),
    )

    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("exchange", sa.String(length=40), nullable=False),
        sa.Column("asset_type", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"], name="fk_instruments_market_id"),
        sa.UniqueConstraint("market_id", "symbol", name="uq_instruments_market_symbol"),
    )
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"])

    op.create_table(
        "daily_prices",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("high_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("low_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("close_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("trading_value", sa.Numeric(24, 4), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("is_adjusted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_daily_prices_instrument_id",
        ),
        sa.UniqueConstraint(
            "instrument_id",
            "trade_date",
            "provider",
            "is_adjusted",
            name="uq_daily_prices_identity",
        ),
    )
    op.create_index("ix_daily_prices_trade_date", "daily_prices", ["trade_date"])
    op.create_index(
        "ix_daily_prices_instrument_date",
        "daily_prices",
        ["instrument_id", "trade_date"],
    )

    op.create_table(
        "data_import_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("job_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
    )
    op.create_index("ix_data_import_jobs_provider", "data_import_jobs", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_data_import_jobs_provider", table_name="data_import_jobs")
    op.drop_table("data_import_jobs")
    op.drop_index("ix_daily_prices_instrument_date", table_name="daily_prices")
    op.drop_index("ix_daily_prices_trade_date", table_name="daily_prices")
    op.drop_table("daily_prices")
    op.drop_index("ix_instruments_symbol", table_name="instruments")
    op.drop_table("instruments")
    op.drop_table("markets")

