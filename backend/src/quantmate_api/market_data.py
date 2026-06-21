from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import requests

from quantmate_api.config import load_local_env
from quantmate_api.time_utils import date_from_timestamp_kst, start_of_day_kst, today_kst


load_local_env()


class MarketDataProviderUnavailable(RuntimeError):
    pass


class MarketDataProviderError(RuntimeError):
    pass


SUPPORTED_KRX_MARKETS = {"KOSPI", "KOSDAQ", "KONEX", "ALL"}
KRX_STOCK_BASE_INFO_ENDPOINTS = {
    "KOSPI": "/stk_isu_base_info",
    "KOSDAQ": "/ksq_isu_base_info",
    "KONEX": "/knx_isu_base_info",
}
YAHOO_KOREA_SUFFIX_BY_EXCHANGE = {
    "KOSPI": ".KS",
    "KOSDAQ": ".KQ",
}


def has_krx_open_api_auth_key() -> bool:
    return bool(os.getenv("KRX_OPEN_API_AUTH_KEY", "").strip())


def is_krx_open_api_ready() -> bool:
    return has_krx_open_api_auth_key()


def has_kis_open_api_credentials() -> bool:
    return bool(os.getenv("KIS_APP_KEY", "").strip() and os.getenv("KIS_APP_SECRET", "").strip())


def is_kis_open_api_ready() -> bool:
    return has_kis_open_api_credentials()


def fetch_krx_instruments(
    market: str = "KOSPI",
    limit: int = 50,
    base_date: str | None = None,
) -> list[dict[str, Any]]:
    normalized_market = normalize_krx_market(market)
    safe_limit = max(1, min(limit, 500))

    if normalized_market == "ALL":
        rows: list[dict[str, Any]] = []
        for item_market in ("KOSPI", "KOSDAQ", "KONEX"):
            rows.extend(fetch_krx_instruments(item_market, limit=safe_limit, base_date=base_date))
            if len(rows) >= safe_limit:
                break
        return rows[:safe_limit]

    payload = call_krx_open_api(
        endpoint=KRX_STOCK_BASE_INFO_ENDPOINTS[normalized_market],
        params={"basDd": base_date or default_krx_base_date()},
    )
    rows = payload.get("OutBlock_1", [])

    if not isinstance(rows, list):
        raise MarketDataProviderUnavailable("KRX Open API 응답 형식이 예상과 다릅니다.")

    return [normalize_krx_instrument(row, normalized_market) for row in rows[:safe_limit]]


def fetch_yahoo_daily_prices(
    symbol: str,
    exchange: str = "KOSPI",
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, Any]]:
    try:
        return fetch_yfinance_daily_prices(symbol=symbol, exchange=exchange, start=start, end=end)
    except ImportError:
        return fetch_yahoo_chart_daily_prices(symbol=symbol, exchange=exchange, start=start, end=end)


def fetch_yfinance_daily_prices(
    symbol: str,
    exchange: str = "KOSPI",
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, Any]]:
    return fetch_yfinance_symbol_daily_prices(
        yahoo_symbol=normalize_yahoo_symbol(symbol, exchange),
        start=start,
        end=end,
    )


def fetch_yfinance_symbol_daily_prices(
    yahoo_symbol: str,
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, Any]]:
    import yfinance as yf

    today = today_kst()
    start_date = start or (today - timedelta(days=90))
    end_date = end or today

    if end_date < start_date:
        raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")

    yahoo_symbol = yahoo_symbol.strip().upper()
    end_exclusive = end_date + timedelta(days=1)

    try:
        frame = yf.download(
            yahoo_symbol,
            start=start_date.isoformat(),
            end=end_exclusive.isoformat(),
            progress=False,
            auto_adjust=False,
            threads=False,
        )
    except Exception as exc:
        raise MarketDataProviderUnavailable(f"yfinance 일봉 호출 실패: {exc}") from exc

    if frame.empty:
        return []

    rows: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        close_price = float_value(row_value(row, "Close"))
        if close_price is None:
            continue

        rows.append(
            {
                "symbol": yahoo_symbol,
                "trade_date": index.date().isoformat(),
                "open": float_value(row_value(row, "Open")),
                "high": float_value(row_value(row, "High")),
                "low": float_value(row_value(row, "Low")),
                "close": close_price,
                "adjusted_close": float_value(row_value(row, "Adj Close")),
                "volume": int_value(row_value(row, "Volume")),
                "provider": "Yahoo Finance",
            }
        )

    return rows


def fetch_yahoo_chart_daily_prices(
    symbol: str,
    exchange: str = "KOSPI",
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, Any]]:
    today = today_kst()
    start_date = start or (today - timedelta(days=90))
    end_date = end or today

    if end_date < start_date:
        raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")

    yahoo_symbol = normalize_yahoo_symbol(symbol, exchange)
    period1 = int(start_of_day_kst(start_date).timestamp())
    # Yahoo chart API의 period2는 배타적이라 종료일 다음 날 0시를 사용한다.
    period2 = int(start_of_day_kst(end_date + timedelta(days=1)).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"

    try:
        response = requests.get(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
                ),
            },
            params={
                "period1": str(period1),
                "period2": str(period2),
                "interval": "1d",
                "events": "history",
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise MarketDataProviderUnavailable(f"Yahoo 일봉 호출 실패: {exc}") from exc

    if response.status_code != 200:
        raise MarketDataProviderUnavailable(f"Yahoo 일봉 호출 실패: HTTP {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise MarketDataProviderUnavailable("Yahoo 일봉 JSON 응답을 해석하지 못했습니다.") from exc

    try:
        result = payload["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        quote = result["indicators"]["quote"][0]
        adjusted = (result["indicators"].get("adjclose") or [{}])[0].get("adjclose") or []
    except (KeyError, IndexError, TypeError) as exc:
        error = (payload.get("chart") or {}).get("error")
        message = error.get("description") if isinstance(error, dict) else None
        raise MarketDataProviderUnavailable(message or "Yahoo 일봉 응답 형식이 예상과 다릅니다.") from exc

    rows: list[dict[str, Any]] = []
    for index, timestamp in enumerate(timestamps):
        close_price = list_value(quote.get("close"), index)
        if close_price is None:
            continue

        rows.append(
            {
                "symbol": yahoo_symbol,
                "trade_date": date_from_timestamp_kst(timestamp).isoformat(),
                "open": list_value(quote.get("open"), index),
                "high": list_value(quote.get("high"), index),
                "low": list_value(quote.get("low"), index),
                "close": close_price,
                "adjusted_close": adjusted[index] if index < len(adjusted) else None,
                "volume": list_value(quote.get("volume"), index),
                "provider": "Yahoo Finance",
            }
        )

    return rows


def call_krx_open_api(endpoint: str, params: dict[str, str]) -> dict[str, Any]:
    auth_key = os.getenv("KRX_OPEN_API_AUTH_KEY", "").strip()

    if not auth_key:
        raise MarketDataProviderUnavailable(
            "KRX Open API 인증키가 필요합니다. KRX_OPEN_API_AUTH_KEY를 설정하세요."
        )

    base_url = os.getenv("KRX_OPEN_API_BASE_URL", "https://openapi.krx.co.kr/svc/apis/sto")
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    try:
        response = requests.get(
            url,
            headers={"AUTH_KEY": auth_key, "Accept": "application/json"},
            params=params,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise MarketDataProviderUnavailable(f"KRX Open API 호출 실패: {exc}") from exc

    if response.status_code != 200:
        raise MarketDataProviderUnavailable(
            f"KRX Open API 권한 또는 호출 상태 확인 필요: HTTP {response.status_code}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise MarketDataProviderUnavailable("KRX Open API JSON 응답을 해석하지 못했습니다.") from exc

    if payload.get("respCode") and payload.get("respCode") != "000":
        message = payload.get("respMsg") or "KRX Open API 응답 오류"
        raise MarketDataProviderUnavailable(f"{message} ({payload['respCode']})")

    return payload


def normalize_krx_instrument(row: dict[str, Any], market: str) -> dict[str, Any]:
    return {
        "symbol": row.get("ISU_SRT_CD") or row.get("ISU_CD") or "",
        "name": row.get("ISU_ABBRV") or row.get("ISU_NM") or "",
        "exchange": row.get("MKT_TP_NM") or market,
        "asset_type": "stock",
    }


def normalize_krx_market(market: str) -> str:
    normalized = market.strip().upper()

    if normalized not in SUPPORTED_KRX_MARKETS:
        supported = ", ".join(sorted(SUPPORTED_KRX_MARKETS))
        raise ValueError(f"지원하지 않는 KRX 시장입니다: {market}. 사용 가능: {supported}")

    return normalized


def normalize_yahoo_symbol(symbol: str, exchange: str = "KOSPI") -> str:
    cleaned = symbol.strip().upper()

    if "." in cleaned:
        return cleaned

    normalized_exchange = exchange.strip().upper()
    suffix = YAHOO_KOREA_SUFFIX_BY_EXCHANGE.get(normalized_exchange, ".KS")

    return f"{cleaned}{suffix}"


def list_value(values: Any, index: int) -> Any:
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def row_value(row: Any, column: str) -> Any:
    if getattr(row.index, "nlevels", 1) > 1:
        for key in row.index:
            if isinstance(key, tuple) and key and key[0] == column:
                return row[key]
    elif column in row:
        return row[column]

    return None


def float_value(value: Any) -> float | None:
    if value is None or value != value:
        return None
    return float(value)


def int_value(value: Any) -> int | None:
    if value is None or value != value:
        return None
    return int(value)


def default_krx_base_date() -> str:
    candidate = today_kst()

    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)

    return candidate.strftime("%Y%m%d")
