"""백테스트 실행 결과 테이블

Revision ID: 0003_backtest_runs
Revises: 0002_user_strategies
Create Date: 2026-06-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_backtest_runs"
down_revision = "0002_user_strategies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("strategy_code", sa.String(length=80), nullable=False),
        sa.Column("strategy_name", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=60), nullable=False),
        sa.Column("start_year", sa.Integer(), nullable=False),
        sa.Column("end_year", sa.Integer(), nullable=False),
        sa.Column("initial_amount", sa.BigInteger(), nullable=False),
        sa.Column("final_amount", sa.BigInteger(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_backtest_runs_strategy_code", "backtest_runs", ["strategy_code"])
    op.create_index("ix_backtest_runs_created_at", "backtest_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_backtest_runs_created_at", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_strategy_code", table_name="backtest_runs")
    op.drop_table("backtest_runs")
