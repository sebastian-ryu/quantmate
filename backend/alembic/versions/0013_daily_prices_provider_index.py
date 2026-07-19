"""daily_prices provider/is_adjusted 복합 인덱스 추가

대용량 daily_prices(NAS 기준 900만+ 행)에서 provider IN (...) + is_adjusted 필터로
instrument_id 단위 최신 거래일/커버리지를 집계하는 쿼리들이 provider 선두 인덱스가 없어
전체 테이블 스캔으로 떨어지던 문제를 해소한다.

대상 쿼리: 시드 후보 산출(_stored_price_seed_candidates), 데이터 품질 커버리지/제공처 집계
(data_quality), 후보/백테스트 가격 로딩의 provider 필터.

Revision ID: 0013_dp_provider_idx
Revises: 0012_fund_current
Create Date: 2026-07-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013_dp_provider_idx"
down_revision = "0012_fund_current"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_daily_prices_provider_adj_instrument_date"
TABLE_NAME = "daily_prices"
COLUMNS = ["provider", "is_adjusted", "instrument_id", "trade_date"]


def upgrade() -> None:
    if not _index_exists(INDEX_NAME):
        op.create_index(INDEX_NAME, TABLE_NAME, COLUMNS)


def downgrade() -> None:
    if _index_exists(INDEX_NAME):
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)


def _index_exists(index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    existing = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    return index_name in existing
