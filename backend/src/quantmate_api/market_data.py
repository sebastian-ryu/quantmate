from __future__ import annotations

import importlib.util
import os
from typing import Any


class MarketDataProviderUnavailable(RuntimeError):
    pass


SUPPORTED_KRX_MARKETS = {"KOSPI", "KOSDAQ", "KONEX", "ALL"}


def is_pykrx_installed() -> bool:
    return importlib.util.find_spec("pykrx") is not None


def has_krx_credentials() -> bool:
    return bool(os.getenv("KRX_ID") and os.getenv("KRX_PW"))


def is_pykrx_ready() -> bool:
    return is_pykrx_installed() and has_krx_credentials()


def fetch_krx_instruments(market: str = "KOSPI", limit: int = 50) -> list[dict[str, Any]]:
    stock = get_pykrx_stock_module()
    normalized_market = normalize_krx_market(market)
    safe_limit = max(1, min(limit, 500))

    tickers = stock.get_market_ticker_list(market=normalized_market)
    rows: list[dict[str, Any]] = []

    for ticker in tickers[:safe_limit]:
        rows.append(
            {
                "symbol": ticker,
                "name": stock.get_market_ticker_name(ticker),
                "exchange": normalized_market,
                "asset_type": "stock",
            }
        )

    return rows


def get_pykrx_stock_module() -> Any:
    if not has_krx_credentials():
        raise MarketDataProviderUnavailable(
            "pykrx KRX 데이터 호출에는 KRX_ID/KRX_PW 환경변수가 필요합니다."
        )

    try:
        from pykrx import stock
    except ModuleNotFoundError as exc:
        raise MarketDataProviderUnavailable(
            "pykrx가 설치되어 있지 않습니다. `make install-backend`를 먼저 실행하세요."
        ) from exc

    return stock


def normalize_krx_market(market: str) -> str:
    normalized = market.strip().upper()

    if normalized not in SUPPORTED_KRX_MARKETS:
        supported = ", ".join(sorted(SUPPORTED_KRX_MARKETS))
        raise ValueError(f"지원하지 않는 KRX 시장입니다: {market}. 사용 가능: {supported}")

    return normalized
