from __future__ import annotations

import os
import time
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
KIS_PROVIDER_NAME = "KIS Open API"
KIS_REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"
KIS_PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"
KIS_DOMESTIC_CURRENT_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
KIS_DOMESTIC_DAILY_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
KIS_DOMESTIC_MARKET_CAP_RANKING_PATH = "/uapi/domestic-stock/v1/ranking/market-cap"
KIS_DOMESTIC_INVESTOR_TRADE_DAILY_PATH = "/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily"
KIS_DOMESTIC_DAILY_SHORT_SALE_PATH = "/uapi/domestic-stock/v1/quotations/daily-short-sale"
KIS_DOMESTIC_DAILY_CREDIT_BALANCE_PATH = "/uapi/domestic-stock/v1/quotations/daily-credit-balance"
KIS_MARKET_CAP_RANKING_MARKET_CODES = {
    "ALL": "0000",
    "KOSPI": "0001",
    "KOSDAQ": "1001",
    "KOSPI200": "2001",
}
KIS_TOKEN_CACHE: dict[str, Any] = {}
KIS_MARKET_CAP_RANKING_CACHE: dict[str, dict[str, Any]] = {}


def has_krx_open_api_auth_key() -> bool:
    return bool(os.getenv("KRX_OPEN_API_AUTH_KEY", "").strip())


def is_krx_open_api_ready() -> bool:
    return has_krx_open_api_auth_key()


def has_kis_open_api_credentials() -> bool:
    return bool(os.getenv("KIS_APP_KEY", "").strip() and os.getenv("KIS_APP_SECRET", "").strip())


def is_kis_open_api_ready() -> bool:
    return has_kis_open_api_credentials()


def is_kis_paper_trading() -> bool:
    return os.getenv("KIS_IS_PAPER", "true").strip().lower() in {"1", "true", "yes", "on"}


def get_kis_base_url() -> str:
    configured = os.getenv("KIS_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")

    return KIS_PAPER_BASE_URL if is_kis_paper_trading() else KIS_REAL_BASE_URL


def get_kis_environment_name() -> str:
    return "paper" if is_kis_paper_trading() else "real"


def get_kis_access_token(force_refresh: bool = False) -> str:
    app_key = os.getenv("KIS_APP_KEY", "").strip()
    app_secret = os.getenv("KIS_APP_SECRET", "").strip()

    if not app_key or not app_secret:
        raise MarketDataProviderUnavailable("KIS_APP_KEY와 KIS_APP_SECRET을 설정하세요.")

    base_url = get_kis_base_url()
    cache_key = f"{base_url}:{app_key}"
    cached = KIS_TOKEN_CACHE.get(cache_key)
    now = time.time()

    if (
        not force_refresh
        and isinstance(cached, dict)
        and cached.get("access_token")
        and float(cached.get("expires_at_epoch", 0)) > now + 60
    ):
        return str(cached["access_token"])

    payload = issue_kis_access_token(app_key=app_key, app_secret=app_secret, base_url=base_url)
    access_token = str(payload.get("access_token") or "")

    if not access_token:
        raise MarketDataProviderUnavailable("KIS 접근토큰 응답에 access_token이 없습니다.")

    expires_in = int_value(payload.get("expires_in")) or 24 * 60 * 60
    KIS_TOKEN_CACHE[cache_key] = {
        "access_token": access_token,
        "expires_at_epoch": now + max(expires_in - 60, 60),
        "token_type": payload.get("token_type", "Bearer"),
    }
    return access_token


def issue_kis_access_token(*, app_key: str, app_secret: str, base_url: str) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/oauth2/tokenP",
            headers={"content-type": "application/json"},
            json={
                "grant_type": "client_credentials",
                "appkey": app_key,
                "appsecret": app_secret,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise MarketDataProviderUnavailable(f"KIS 접근토큰 발급 실패: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise MarketDataProviderUnavailable("KIS 접근토큰 JSON 응답을 해석하지 못했습니다.") from exc

    if response.status_code != 200:
        message = payload.get("error_description") or payload.get("msg1") or response.text
        raise MarketDataProviderUnavailable(f"KIS 접근토큰 발급 실패: HTTP {response.status_code} {message}")

    return payload


def get_kis_token_status() -> dict[str, Any]:
    base_url = get_kis_base_url()
    app_key = os.getenv("KIS_APP_KEY", "").strip()
    cache_key = f"{base_url}:{app_key}"
    cached = KIS_TOKEN_CACHE.get(cache_key)
    expires_at = float(cached.get("expires_at_epoch", 0)) if isinstance(cached, dict) else 0

    return {
        "provider": KIS_PROVIDER_NAME,
        "ready": is_kis_open_api_ready(),
        "environment": get_kis_environment_name(),
        "base_url": base_url,
        "token_cached": bool(expires_at > time.time()),
        "expires_in_seconds": max(0, int(expires_at - time.time())) if expires_at else 0,
    }


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


def fetch_kis_current_price(symbol: str) -> dict[str, Any]:
    normalized_symbol = normalize_kis_symbol(symbol)
    payload = call_kis_open_api(
        path=KIS_DOMESTIC_CURRENT_PRICE_PATH,
        tr_id="FHKST01010100",
        params={
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": normalized_symbol,
        },
    )
    output = payload.get("output")

    if not isinstance(output, dict):
        raise MarketDataProviderUnavailable("KIS 현재가 응답 형식이 예상과 다릅니다.")

    return {
        "provider": KIS_PROVIDER_NAME,
        "symbol": normalized_symbol,
        "name": str(output.get("hts_kor_isnm") or normalized_symbol),
        "price": int_from_kis(output.get("stck_prpr")),
        "change": int_from_kis(output.get("prdy_vrss")),
        "change_rate": float_from_kis(output.get("prdy_ctrt")),
        "volume": int_from_kis(output.get("acml_vol")),
        "trading_value": int_from_kis(output.get("acml_tr_pbmn")),
        "open": int_from_kis(output.get("stck_oprc")),
        "high": int_from_kis(output.get("stck_hgpr")),
        "low": int_from_kis(output.get("stck_lwpr")),
        "market_state": str(output.get("iscd_stat_cls_code") or ""),
        "market_cap": int_from_kis(output.get("hts_avls")),
        "per": float_from_kis(output.get("per")),
        "pbr": float_from_kis(output.get("pbr")),
        "eps": float_from_kis(output.get("eps")),
        "bps": float_from_kis(output.get("bps")),
        "turnover_pct": float_from_kis(output.get("vol_tnrt")),
        "foreign_holding_rate": float_from_kis(output.get("hts_frgn_ehrt")),
        "foreign_net_buy_qty": int_from_kis(output.get("frgn_ntby_qty")),
        "program_net_buy_qty": int_from_kis(output.get("pgtr_ntby_qty")),
        "high_52w": int_from_kis(output.get("w52_hgpr")),
        "low_52w": int_from_kis(output.get("w52_lwpr")),
    }


def fetch_kis_daily_prices(
    symbol: str,
    start: date | None = None,
    end: date | None = None,
    is_adjusted: bool = False,
) -> list[dict[str, Any]]:
    today = today_kst()
    start_date = start or (today - timedelta(days=90))
    end_date = end or today

    if end_date < start_date:
        raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")

    normalized_symbol = normalize_kis_symbol(symbol)
    payload = call_kis_open_api(
        path=KIS_DOMESTIC_DAILY_PRICE_PATH,
        tr_id="FHKST03010100",
        params={
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": normalized_symbol,
            "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "0" if is_adjusted else "1",
        },
    )
    rows = payload.get("output2")

    if not isinstance(rows, list):
        raise MarketDataProviderUnavailable("KIS 일봉 응답 형식이 예상과 다릅니다.")

    normalized_rows = [
        normalize_kis_daily_price(row=row, symbol=normalized_symbol, is_adjusted=is_adjusted)
        for row in rows
        if isinstance(row, dict)
    ]
    return [row for row in normalized_rows if row is not None]


def fetch_kis_market_cap_ranking(limit: int = 50, market: str = "ALL") -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 100))
    normalized_market = market.strip().upper()
    cache_key = f"{get_kis_base_url()}:{normalized_market}:{safe_limit}"
    cached = KIS_MARKET_CAP_RANKING_CACHE.get(cache_key)
    if isinstance(cached, dict) and float(cached.get("expires_at_epoch", 0)) > time.time():
        rows = cached.get("rows")
        if isinstance(rows, list):
            return [dict(row) for row in rows]

    if normalized_market not in KIS_MARKET_CAP_RANKING_MARKET_CODES:
        supported = ", ".join(sorted(KIS_MARKET_CAP_RANKING_MARKET_CODES))
        raise ValueError(f"지원하지 않는 KIS 시가총액 시장입니다: {market}. 사용 가능: {supported}")

    if normalized_market == "ALL":
        rows: list[dict[str, Any]] = []
        errors: list[MarketDataProviderUnavailable] = []

        for item_market in ("KOSPI", "KOSDAQ"):
            try:
                rows.extend(fetch_kis_market_cap_ranking(limit=safe_limit, market=item_market))
            except MarketDataProviderUnavailable as exc:
                errors.append(exc)

        if not rows and errors:
            raise errors[0]

        combined_rows = sorted(
            rows,
            key=lambda item: int(item.get("market_cap") or 0),
            reverse=True,
        )[:safe_limit]
        KIS_MARKET_CAP_RANKING_CACHE[cache_key] = {
            "rows": combined_rows,
            "expires_at_epoch": time.time() + 10 * 60,
        }
        return [dict(row) for row in combined_rows]

    payload = call_kis_open_api(
        path=KIS_DOMESTIC_MARKET_CAP_RANKING_PATH,
        tr_id="FHPST01740000",
        params={
            "fid_input_price_2": "",
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20174",
            "fid_div_cls_code": "0",
            "fid_input_iscd": KIS_MARKET_CAP_RANKING_MARKET_CODES[normalized_market],
            "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0",
            "fid_input_price_1": "",
            "fid_vol_cnt": "",
        },
    )
    rows = payload.get("output")

    if not isinstance(rows, list):
        raise MarketDataProviderUnavailable("KIS 시가총액 상위 응답 형식이 예상과 다릅니다.")

    normalized_rows = [
        normalize_kis_market_cap_ranking(row, exchange=normalized_market)
        for row in rows[:safe_limit]
        if isinstance(row, dict)
    ]
    result_rows = [row for row in normalized_rows if row is not None]
    KIS_MARKET_CAP_RANKING_CACHE[cache_key] = {
        "rows": result_rows,
        "expires_at_epoch": time.time() + 10 * 60,
    }
    return [dict(row) for row in result_rows]


def fetch_kis_investor_trade_daily(
    symbol: str,
    base_date: date | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    normalized_symbol = normalize_kis_symbol(symbol)
    safe_limit = max(1, min(limit, 100))
    input_date = base_date or today_kst()
    payload = call_kis_open_api(
        path=KIS_DOMESTIC_INVESTOR_TRADE_DAILY_PATH,
        tr_id="FHPTJ04160001",
        params={
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": normalized_symbol,
            "FID_INPUT_DATE_1": input_date.strftime("%Y%m%d"),
            "FID_ORG_ADJ_PRC": "",
            "FID_ETC_CLS_CODE": "",
        },
    )
    rows = payload.get("output2") or payload.get("output")

    if not isinstance(rows, list):
        raise MarketDataProviderUnavailable("KIS 투자자별 매매동향 응답 형식이 예상과 다릅니다.")

    normalized_rows = [
        normalize_kis_investor_trade_daily(row=row, symbol=normalized_symbol)
        for row in rows[:safe_limit]
        if isinstance(row, dict)
    ]
    return [row for row in normalized_rows if row is not None]


def fetch_kis_daily_short_sale(
    symbol: str,
    start: date | None = None,
    end: date | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    today = today_kst()
    start_date = start or (today - timedelta(days=45))
    end_date = end or today

    if end_date < start_date:
        raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")

    normalized_symbol = normalize_kis_symbol(symbol)
    safe_limit = max(1, min(limit, 100))
    payload = call_kis_open_api(
        path=KIS_DOMESTIC_DAILY_SHORT_SALE_PATH,
        tr_id="FHPST04830000",
        params={
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": normalized_symbol,
            "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
        },
    )
    rows = payload.get("output2") or payload.get("output")

    if not isinstance(rows, list):
        raise MarketDataProviderUnavailable("KIS 공매도 일별추이 응답 형식이 예상과 다릅니다.")

    normalized_rows = [
        normalize_kis_daily_short_sale(row=row, symbol=normalized_symbol)
        for row in rows[:safe_limit]
        if isinstance(row, dict)
    ]
    return [row for row in normalized_rows if row is not None]


def fetch_kis_daily_credit_balance(
    symbol: str,
    base_date: date | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    normalized_symbol = normalize_kis_symbol(symbol)
    safe_limit = max(1, min(limit, 100))
    input_date = base_date or today_kst()
    payload = call_kis_open_api(
        path=KIS_DOMESTIC_DAILY_CREDIT_BALANCE_PATH,
        tr_id="FHPST04760000",
        params={
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20476",
            "FID_INPUT_ISCD": normalized_symbol,
            "FID_INPUT_DATE_1": input_date.strftime("%Y%m%d"),
        },
    )
    rows = payload.get("output")

    if not isinstance(rows, list):
        raise MarketDataProviderUnavailable("KIS 신용잔고 일별추이 응답 형식이 예상과 다릅니다.")

    normalized_rows = [
        normalize_kis_daily_credit_balance(row=row, symbol=normalized_symbol)
        for row in rows[:safe_limit]
        if isinstance(row, dict)
    ]
    return [row for row in normalized_rows if row is not None]


def call_kis_open_api(
    *,
    path: str,
    tr_id: str,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    app_key = os.getenv("KIS_APP_KEY", "").strip()
    app_secret = os.getenv("KIS_APP_SECRET", "").strip()

    if not app_key or not app_secret:
        raise MarketDataProviderUnavailable("KIS_APP_KEY와 KIS_APP_SECRET을 설정하세요.")

    try:
        response = requests.get(
            f"{get_kis_base_url().rstrip('/')}/{path.lstrip('/')}",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {get_kis_access_token()}",
                "appkey": app_key,
                "appsecret": app_secret,
                "tr_id": tr_id,
                "custtype": "P",
            },
            params=params or {},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise MarketDataProviderUnavailable(f"KIS Open API 호출 실패: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise MarketDataProviderUnavailable("KIS Open API JSON 응답을 해석하지 못했습니다.") from exc

    if response.status_code != 200:
        message = payload.get("msg1") or payload.get("error_description") or response.text
        raise MarketDataProviderUnavailable(f"KIS Open API 호출 실패: HTTP {response.status_code} {message}")

    if payload.get("rt_cd") not in (None, "0"):
        message = payload.get("msg1") or "KIS Open API 응답 오류"
        code = payload.get("msg_cd") or payload.get("rt_cd")
        raise MarketDataProviderUnavailable(f"{message} ({code})")

    return payload


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


def normalize_kis_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()

    if not normalized:
        raise ValueError("종목코드를 입력하세요.")

    return normalized


def normalize_kis_daily_price(
    *,
    row: dict[str, Any],
    symbol: str,
    is_adjusted: bool,
) -> dict[str, Any] | None:
    trade_date = str(row.get("stck_bsop_date") or "").strip()
    close_price = float_from_kis(row.get("stck_clpr"))

    if not trade_date or close_price is None:
        return None

    return {
        "symbol": symbol,
        "trade_date": f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}",
        "open": float_from_kis(row.get("stck_oprc")) or close_price,
        "high": float_from_kis(row.get("stck_hgpr")) or close_price,
        "low": float_from_kis(row.get("stck_lwpr")) or close_price,
        "close": close_price,
        "adjusted_close": close_price if is_adjusted else None,
        "volume": int_from_kis(row.get("acml_vol")) or 0,
        "trading_value": int_from_kis(row.get("acml_tr_pbmn")),
        "provider": KIS_PROVIDER_NAME,
    }


def normalize_kis_market_cap_ranking(row: dict[str, Any], exchange: str = "KR") -> dict[str, Any] | None:
    symbol = str(row.get("mksc_shrn_iscd") or "").strip().upper()
    if not symbol:
        return None

    return {
        "provider": KIS_PROVIDER_NAME,
        "symbol": symbol,
        "name": str(row.get("hts_kor_isnm") or symbol),
        "exchange": exchange,
        "price": int_from_kis(row.get("stck_prpr")),
        "change_rate": float_from_kis(row.get("prdy_ctrt")),
        "volume": int_from_kis(row.get("acml_vol")),
        "market_cap": int_from_kis(row.get("stck_avls")),
        "listed_shares": int_from_kis(row.get("lstn_stcn")),
        "market_cap_weight": float_from_kis(row.get("mrkt_whol_avls_rlim")),
        "rank": int_from_kis(row.get("data_rank")),
    }


def normalize_kis_investor_trade_daily(
    *,
    row: dict[str, Any],
    symbol: str,
) -> dict[str, Any] | None:
    trade_date = str(row.get("stck_bsop_date") or "").strip()
    if not trade_date:
        return None

    return {
        "provider": KIS_PROVIDER_NAME,
        "symbol": symbol,
        "trade_date": f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}",
        "foreign_net_buy_qty": int_from_kis(row.get("frgn_ntby_qty")),
        "institution_net_buy_qty": int_from_kis(row.get("orgn_ntby_qty")),
        "pension_net_buy_qty": int_from_kis(row.get("fund_ntby_qty")),
        "foreign_net_buy_value": int_from_kis(row.get("frgn_ntby_tr_pbmn")),
        "institution_net_buy_value": int_from_kis(row.get("orgn_ntby_tr_pbmn")),
        "pension_net_buy_value": int_from_kis(row.get("fund_ntby_tr_pbmn")),
        "individual_net_buy_value": int_from_kis(row.get("prsn_ntby_tr_pbmn")),
    }


def normalize_kis_daily_short_sale(
    *,
    row: dict[str, Any],
    symbol: str,
) -> dict[str, Any] | None:
    trade_date = str(row.get("stck_bsop_date") or "").strip()
    if not trade_date:
        return None

    return {
        "provider": KIS_PROVIDER_NAME,
        "symbol": symbol,
        "trade_date": f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}",
        "short_sale_volume": int_from_kis(row.get("ssts_cntg_qty")),
        "short_sale_volume_ratio": float_from_kis(row.get("ssts_vol_rlim")),
        "short_sale_value": int_from_kis(row.get("ssts_tr_pbmn")),
        "short_sale_value_ratio": float_from_kis(row.get("ssts_tr_pbmn_rlim")),
    }


def normalize_kis_daily_credit_balance(
    *,
    row: dict[str, Any],
    symbol: str,
) -> dict[str, Any] | None:
    trade_date = str(row.get("deal_date") or row.get("stlm_date") or "").strip()
    if not trade_date:
        return None

    return {
        "provider": KIS_PROVIDER_NAME,
        "symbol": symbol,
        "trade_date": f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}",
        "margin_loan_balance": int_from_kis(row.get("whol_loan_rmnd_amt")),
        "margin_loan_balance_rate": float_from_kis(row.get("whol_loan_rmnd_rate")),
        "margin_loan_new_amount": int_from_kis(row.get("whol_loan_new_amt")),
        "margin_loan_redeem_amount": int_from_kis(row.get("whol_loan_rdmp_amt")),
        "stock_loan_balance": int_from_kis(row.get("whol_stln_rmnd_amt")),
        "stock_loan_balance_rate": float_from_kis(row.get("whol_stln_rmnd_rate")),
    }


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


def float_from_kis(value: Any) -> float | None:
    if value is None:
        return None

    cleaned = str(value).strip().replace(",", "")
    if not cleaned:
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def int_from_kis(value: Any) -> int | None:
    parsed = float_from_kis(value)
    if parsed is None:
        return None

    return int(parsed)


def default_krx_base_date() -> str:
    candidate = today_kst()

    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)

    return candidate.strftime("%Y%m%d")
