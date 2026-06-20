from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from quantmate_api.db import SessionLocal
from quantmate_api.models import Instrument, Market


DEMO_INSTRUMENTS = [
    {"symbol": "005930", "name": "삼성전자", "exchange": "KOSPI", "asset_type": "stock"},
    {"symbol": "000660", "name": "SK하이닉스", "exchange": "KOSPI", "asset_type": "stock"},
    {"symbol": "035720", "name": "카카오", "exchange": "KOSPI", "asset_type": "stock"},
]


def seed_reference_data(session: Session) -> None:
    market = session.scalar(select(Market).where(Market.code == "KR"))
    if market is None:
        market = Market(
            code="KR",
            name="한국 주식",
            country="KR",
            currency="KRW",
            timezone="Asia/Seoul",
        )
        session.add(market)
        session.flush()

    existing_symbols = set(
        session.scalars(
            select(Instrument.symbol).where(
                Instrument.market_id == market.id,
                Instrument.symbol.in_([item["symbol"] for item in DEMO_INSTRUMENTS]),
            )
        )
    )

    for item in DEMO_INSTRUMENTS:
        if item["symbol"] in existing_symbols:
            continue
        session.add(
            Instrument(
                market_id=market.id,
                symbol=item["symbol"],
                name=item["name"],
                exchange=item["exchange"],
                asset_type=item["asset_type"],
            )
        )

    session.commit()


def main() -> None:
    with SessionLocal() as session:
        seed_reference_data(session)
    print("Seeded QuantMate reference data.")


if __name__ == "__main__":
    main()

