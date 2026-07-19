"""전략 후보 산출 결과 캐시 테이블 추가

전략 페이지 진입/전략 선택 시 시드 조회 + 일봉 로딩 + 스코어링을 매번 다시 하지 않도록,
산출된 후보 응답을 (전략 코드, limit)별로 저장한다. 데이터 지문이 그대로면 재계산을 건너뛴다.

Revision ID: 0015_cand_snapshots
Revises: 0014_data_status_snap
Create Date: 2026-07-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0015_cand_snapshots"
down_revision = "0014_data_status_snap"
branch_labels = None
depends_on = None

TABLE_NAME = "strategy_candidate_snapshots"


def upgrade() -> None:
    if _table_exists(TABLE_NAME):
        return
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("strategy_code", sa.String(length=80), nullable=False),
        sa.Column("result_limit", sa.Integer(), nullable=False),
        sa.Column("data_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "strategy_code", "result_limit", name="uq_strategy_candidate_snapshots_code_limit"
        ),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_strategy_candidate_snapshots_code", TABLE_NAME, ["strategy_code"])


def downgrade() -> None:
    if not _table_exists(TABLE_NAME):
        return
    op.drop_index("ix_strategy_candidate_snapshots_code", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()
