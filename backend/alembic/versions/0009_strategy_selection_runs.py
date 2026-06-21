"""전략 실행 결과 저장 테이블

Revision ID: 0009_strategy_selection_runs
Revises: 0008_broker_audit_logs
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_strategy_selection_runs"
down_revision = "0008_broker_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_selection_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("strategy_code", sa.String(length=80), nullable=False),
        sa.Column("strategy_name", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_strategy_selection_runs_strategy_code",
        "strategy_selection_runs",
        ["strategy_code"],
    )
    op.create_index(
        "ix_strategy_selection_runs_created_at",
        "strategy_selection_runs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_strategy_selection_runs_created_at", table_name="strategy_selection_runs")
    op.drop_index("ix_strategy_selection_runs_strategy_code", table_name="strategy_selection_runs")
    op.drop_table("strategy_selection_runs")
