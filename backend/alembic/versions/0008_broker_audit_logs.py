"""증권사 API 감사 로그 테이블

Revision ID: 0008_broker_audit_logs
Revises: 0007_fundamental_ratios
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_broker_audit_logs"
down_revision = "0007_fundamental_ratios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broker_audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_broker_audit_logs_created_at", "broker_audit_logs", ["created_at"])
    op.create_index(
        "ix_broker_audit_logs_provider_action",
        "broker_audit_logs",
        ["provider", "action"],
    )


def downgrade() -> None:
    op.drop_index("ix_broker_audit_logs_provider_action", table_name="broker_audit_logs")
    op.drop_index("ix_broker_audit_logs_created_at", table_name="broker_audit_logs")
    op.drop_table("broker_audit_logs")
