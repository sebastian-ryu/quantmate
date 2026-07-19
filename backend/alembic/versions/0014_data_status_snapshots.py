"""data_status/data_quality 요약 스냅샷 테이블 추가

대용량 daily_prices 집계(OHLCV 무결성 OR 스캔, 커버리지 HAVING, provider 집계, 전체 COUNT)를
매 요청 실시간으로 계산하면 수백 초가 걸린다. 사전 계산 값을 저장해 화면이 빠르게 읽도록 한다.

Revision ID: 0014_data_status_snap
Revises: 0013_dp_provider_idx
Create Date: 2026-07-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0014_data_status_snap"
down_revision = "0013_dp_provider_idx"
branch_labels = None
depends_on = None

TABLE_NAME = "data_status_snapshots"


def upgrade() -> None:
    if _table_exists(TABLE_NAME):
        return
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("daily_price_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("covered_symbol_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_ohlcv_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("provider_counts_json", sa.Text(), nullable=False),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_data_status_snapshots_computed_at", TABLE_NAME, ["computed_at"]
    )


def downgrade() -> None:
    if not _table_exists(TABLE_NAME):
        return
    op.drop_index("ix_data_status_snapshots_computed_at", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()
