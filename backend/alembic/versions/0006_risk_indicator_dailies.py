"""KIS 일별 리스크 지표 테이블

Revision ID: 0006_risk_indicator_dailies
Revises: 0005_supply_flow_dailies
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_risk_indicator_dailies"
down_revision = "0005_supply_flow_dailies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_indicator_dailies",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("short_sale_volume", sa.BigInteger(), nullable=True),
        sa.Column("short_sale_volume_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("short_sale_value", sa.Numeric(24, 4), nullable=True),
        sa.Column("short_sale_value_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("margin_loan_balance", sa.Numeric(24, 4), nullable=True),
        sa.Column("margin_loan_balance_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("margin_loan_new_amount", sa.Numeric(24, 4), nullable=True),
        sa.Column("margin_loan_redeem_amount", sa.Numeric(24, 4), nullable=True),
        sa.Column("stock_loan_balance", sa.Numeric(24, 4), nullable=True),
        sa.Column("stock_loan_balance_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_risk_indicator_dailies_instrument_id",
        ),
        sa.UniqueConstraint(
            "instrument_id",
            "trade_date",
            "provider",
            name="uq_risk_indicator_dailies_identity",
        ),
    )
    op.create_index("ix_risk_indicator_dailies_trade_date", "risk_indicator_dailies", ["trade_date"])
    op.create_index(
        "ix_risk_indicator_dailies_instrument_date",
        "risk_indicator_dailies",
        ["instrument_id", "trade_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_risk_indicator_dailies_instrument_date", table_name="risk_indicator_dailies")
    op.drop_index("ix_risk_indicator_dailies_trade_date", table_name="risk_indicator_dailies")
    op.drop_table("risk_indicator_dailies")
