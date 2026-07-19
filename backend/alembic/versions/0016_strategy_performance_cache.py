"""전략 성과 스냅샷 캐시 테이블 추가

전략 소개 성과 스냅샷(1/3/5/10년 백테스트)은 전략 6개 × 최대 10년이라 계산이 무겁다(수십 초).
인메모리 캐시만으로는 재시작 때마다 첫 호출이 느리므로 결과를 DB에 저장해 재시작 후에도 즉시 제공한다.

Revision ID: 0016_perf_cache
Revises: 0015_cand_snapshots
Create Date: 2026-07-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0016_perf_cache"
down_revision = "0015_cand_snapshots"
branch_labels = None
depends_on = None

TABLE_NAME = "strategy_performance_cache"


def upgrade() -> None:
    if _table_exists(TABLE_NAME):
        return
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cache_key", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_strategy_performance_cache_computed_at", TABLE_NAME, ["computed_at"])


def downgrade() -> None:
    if not _table_exists(TABLE_NAME):
        return
    op.drop_index("ix_strategy_performance_cache_computed_at", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()
