"""KIS 재무비율 테이블

Revision ID: 0007_fundamental_ratios
Revises: 0006_risk_indicator_dailies
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_fundamental_ratios"
down_revision = "0006_risk_indicator_dailies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fundamental_ratios",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.String(length=10), nullable=False),
        sa.Column("period_type", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("revenue_growth", sa.Numeric(12, 4), nullable=True),
        sa.Column("operating_income_growth", sa.Numeric(12, 4), nullable=True),
        sa.Column("net_income_growth", sa.Numeric(12, 4), nullable=True),
        sa.Column("roe", sa.Numeric(12, 4), nullable=True),
        sa.Column("eps", sa.Numeric(18, 4), nullable=True),
        sa.Column("sps", sa.Numeric(18, 4), nullable=True),
        sa.Column("bps", sa.Numeric(18, 4), nullable=True),
        sa.Column("reserve_ratio", sa.Numeric(12, 4), nullable=True),
        sa.Column("debt_ratio", sa.Numeric(12, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_fundamental_ratios_instrument_id",
        ),
        sa.UniqueConstraint(
            "instrument_id",
            "fiscal_period",
            "period_type",
            "provider",
            name="uq_fundamental_ratios_identity",
        ),
    )
    op.create_index("ix_fundamental_ratios_period", "fundamental_ratios", ["fiscal_period"])
    op.create_index(
        "ix_fundamental_ratios_instrument_period",
        "fundamental_ratios",
        ["instrument_id", "fiscal_period"],
    )


def downgrade() -> None:
    op.drop_index("ix_fundamental_ratios_instrument_period", table_name="fundamental_ratios")
    op.drop_index("ix_fundamental_ratios_period", table_name="fundamental_ratios")
    op.drop_table("fundamental_ratios")
