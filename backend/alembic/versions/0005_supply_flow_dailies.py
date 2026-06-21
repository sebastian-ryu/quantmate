"""KIS 일별 수급 테이블

Revision ID: 0005_supply_flow_dailies
Revises: 0004_quote_snapshots
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_supply_flow_dailies"
down_revision = "0004_quote_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supply_flow_dailies",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("foreign_net_buy_qty", sa.BigInteger(), nullable=True),
        sa.Column("institution_net_buy_qty", sa.BigInteger(), nullable=True),
        sa.Column("pension_net_buy_qty", sa.BigInteger(), nullable=True),
        sa.Column("foreign_net_buy_value", sa.Numeric(24, 4), nullable=True),
        sa.Column("institution_net_buy_value", sa.Numeric(24, 4), nullable=True),
        sa.Column("pension_net_buy_value", sa.Numeric(24, 4), nullable=True),
        sa.Column("individual_net_buy_value", sa.Numeric(24, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_supply_flow_dailies_instrument_id",
        ),
        sa.UniqueConstraint(
            "instrument_id",
            "trade_date",
            "provider",
            name="uq_supply_flow_dailies_identity",
        ),
    )
    op.create_index("ix_supply_flow_dailies_trade_date", "supply_flow_dailies", ["trade_date"])
    op.create_index(
        "ix_supply_flow_dailies_instrument_date",
        "supply_flow_dailies",
        ["instrument_id", "trade_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_supply_flow_dailies_instrument_date", table_name="supply_flow_dailies")
    op.drop_index("ix_supply_flow_dailies_trade_date", table_name="supply_flow_dailies")
    op.drop_table("supply_flow_dailies")
