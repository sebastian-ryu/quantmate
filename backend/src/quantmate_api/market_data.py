from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from quantmate_api.config import load_local_env
from quantmate_api.time_utils import date_from_timestamp_kst, now_kst_naive, start_of_day_kst, today_kst


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
KIS_DOMESTIC_FINANCIAL_RATIO_PATH = "/uapi/domestic-stock/v1/finance/financial-ratio"
KIS_DOMESTIC_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
KIS_DOMESTIC_BUYABLE_CASH_PATH = "/uapi/domestic-stock/v1/trading/inquire-psbl-order"
KIS_DOMESTIC_CASH_ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
KIS_DOMESTIC_DAILY_ORDER_EXECUTION_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
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


def has_kis_account_credentials() -> bool:
    return bool(os.getenv("KIS_ACCOUNT_NO", "").strip() and os.getenv("KIS_ACCOUNT_PRODUCT_CODE", "").strip())


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


def get_kis_env_division() -> str:
    return "demo" if is_kis_paper_trading() else "real"


def get_kis_account_config() -> dict[str, str]:
    account_no = os.getenv("KIS_ACCOUNT_NO", "").strip()
    product_code = os.getenv("KIS_ACCOUNT_PRODUCT_CODE", "").strip()

    if not account_no or not product_code:
        raise MarketDataProviderUnavailable("KIS_ACCOUNT_NO와 KIS_ACCOUNT_PRODUCT_CODE를 설정하세요.")

    return {
        "account_no": account_no,
        "product_code": product_code,
        "account_label": mask_kis_account(account_no=account_no, product_code=product_code),
    }


def mask_kis_account(*, account_no: str, product_code: str = "") -> str:
    normalized = account_no.strip()
    product = product_code.strip()
    if len(normalized) <= 2:
        masked = "*" * len(normalized)
    else:
        masked = f"{'*' * max(len(normalized) - 2, 0)}{normalized[-2:]}"
    return f"{masked}-{product}" if product else masked


def get_kis_token_cache_path() -> Path:
    configured = os.getenv("KIS_TOKEN_CACHE_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()

    return Path(__file__).resolve().parents[3] / ".run" / "kis_token_cache.json"


def read_kis_token_file_cache(cache_key: str, now: float) -> dict[str, Any] | None:
    path = get_kis_token_cache_path()
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    if payload.get("cache_key") != cache_key:
        return None
    if not payload.get("access_token"):
        return None
    if float(payload.get("expires_at_epoch", 0)) <= now + 60:
        return None

    return payload


def write_kis_token_file_cache(cache_key: str, cache_record: dict[str, Any]) -> None:
    path = get_kis_token_cache_path()
    payload = {
        "cache_key": cache_key,
        **cache_record,
    }

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        path.chmod(0o600)
    except OSError:
        return


def get_kis_access_token(force_refresh: bool = False) -> str:
    app_key = os.getenv("KIS_APP_KEY", "").strip()
    app_secret = os.getenv("KIS_APP_SECRET", "").strip()

    if not app_key or not app_secret:
        raise MarketDataProviderUnavailable("KIS_APP_KEY와 KIS_APP_SECRET을 설정하세요.")

    configured_token = os.getenv("KIS_ACCESS_TOKEN", "").strip()
    if configured_token and not force_refresh:
        return configured_token

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

    file_cached = None if force_refresh else read_kis_token_file_cache(cache_key=cache_key, now=now)
    if file_cached is not None:
        KIS_TOKEN_CACHE[cache_key] = file_cached
        return str(file_cached["access_token"])

    payload = issue_kis_access_token(app_key=app_key, app_secret=app_secret, base_url=base_url)
    access_token = str(payload.get("access_token") or "")

    if not access_token:
        raise MarketDataProviderUnavailable("KIS 접근토큰 응답에 access_token이 없습니다.")

    expires_in = int_value(payload.get("expires_in")) or 24 * 60 * 60
    cache_record = {
        "access_token": access_token,
        "expires_at_epoch": now + max(expires_in - 60, 60),
        "token_type": payload.get("token_type", "Bearer"),
    }
    KIS_TOKEN_CACHE[cache_key] = cache_record
    write_kis_token_file_cache(cache_key=cache_key, cache_record=cache_record)
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
    configured_token = os.getenv("KIS_ACCESS_TOKEN", "").strip()
    cache_key = f"{base_url}:{app_key}"
    cached = KIS_TOKEN_CACHE.get(cache_key)
    expires_at = float(cached.get("expires_at_epoch", 0)) if isinstance(cached, dict) else 0
    file_cached = read_kis_token_file_cache(cache_key=cache_key, now=time.time()) if app_key else None
    file_expires_at = float(file_cached.get("expires_at_epoch", 0)) if isinstance(file_cached, dict) else 0
    effective_expires_at = max(expires_at, file_expires_at)

    return {
        "provider": KIS_PROVIDER_NAME,
        "ready": is_kis_open_api_ready(),
        "environment": get_kis_environment_name(),
        "base_url": base_url,
        "token_cached": bool(configured_token or effective_expires_at > time.time()),
        "expires_in_seconds": max(0, int(effective_expires_at - time.time())) if effective_expires_at else 0,
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


def fetch_kis_financial_ratios(
    symbol: str,
    period_type: str = "annual",
    limit: int = 8,
) -> list[dict[str, Any]]:
    normalized_symbol = normalize_kis_symbol(symbol)
    normalized_period_type = period_type.strip().lower()
    period_code_by_type = {
        "annual": "0",
        "year": "0",
        "yearly": "0",
        "quarter": "1",
        "quarterly": "1",
    }
    period_code = period_code_by_type.get(normalized_period_type)
    if period_code is None:
        raise ValueError("재무비율 기간은 annual 또는 quarter만 사용할 수 있습니다.")

    safe_limit = max(1, min(limit, 20))
    payload = call_kis_open_api(
        path=KIS_DOMESTIC_FINANCIAL_RATIO_PATH,
        tr_id="FHKST66430300",
        params={
            "FID_DIV_CLS_CODE": period_code,
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": normalized_symbol,
        },
    )
    rows = payload.get("output")

    if not isinstance(rows, list):
        rows = [rows] if isinstance(rows, dict) else []

    normalized_rows = [
        normalize_kis_financial_ratio(
            row=row,
            symbol=normalized_symbol,
            period_type="annual" if period_code == "0" else "quarter",
        )
        for row in rows[:safe_limit]
        if isinstance(row, dict)
    ]
    return [row for row in normalized_rows if row is not None]


def fetch_kis_domestic_balance(max_pages: int = 5) -> dict[str, Any]:
    account = get_kis_account_config()
    tr_id = "VTTC8434R" if is_kis_paper_trading() else "TTTC8434R"
    safe_max_pages = max(1, min(max_pages, 20))
    holdings: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    ctx_area_fk100 = ""
    ctx_area_nk100 = ""
    tr_cont = ""

    for _page in range(safe_max_pages):
        payload, headers = request_kis_open_api(
            method="GET",
            path=KIS_DOMESTIC_BALANCE_PATH,
            tr_id=tr_id,
            tr_cont=tr_cont,
            params={
                "CANO": account["account_no"],
                "ACNT_PRDT_CD": account["product_code"],
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": ctx_area_fk100,
                "CTX_AREA_NK100": ctx_area_nk100,
            },
        )
        raw_holdings = payload.get("output1") or []
        raw_summary = payload.get("output2") or []
        if isinstance(raw_holdings, list):
            holdings.extend(normalize_kis_balance_holding(row) for row in raw_holdings if isinstance(row, dict))
        if isinstance(raw_summary, list) and raw_summary:
            summary = normalize_kis_balance_summary(raw_summary[0])
        elif isinstance(raw_summary, dict):
            summary = normalize_kis_balance_summary(raw_summary)

        ctx_area_fk100 = str(payload.get("ctx_area_fk100") or "")
        ctx_area_nk100 = str(payload.get("ctx_area_nk100") or "")
        response_tr_cont = str(headers.get("tr_cont") or "").strip()
        if response_tr_cont not in {"M", "F"}:
            break
        tr_cont = "N"

    visible_holdings = [
        holding
        for holding in holdings
        if (holding.get("holding_quantity") or 0) > 0 or (holding.get("evaluation_amount") or 0) > 0
    ]
    return {
        "provider": KIS_PROVIDER_NAME,
        "environment": get_kis_environment_name(),
        "account_label": account["account_label"],
        "fetched_at": now_kst_naive().isoformat(timespec="seconds"),
        "summary": summary,
        "holdings": visible_holdings,
    }


def fetch_kis_buyable_cash(
    *,
    symbol: str,
    order_price: int = 0,
    order_type: str = "market",
) -> dict[str, Any]:
    account = get_kis_account_config()
    normalized_symbol = normalize_kis_symbol(symbol)
    normalized_order_type = order_type.strip().lower()
    order_division = "01" if normalized_order_type == "market" else "00"
    tr_id = "VTTC8908R" if is_kis_paper_trading() else "TTTC8908R"
    payload = call_kis_open_api(
        path=KIS_DOMESTIC_BUYABLE_CASH_PATH,
        tr_id=tr_id,
        params={
            "CANO": account["account_no"],
            "ACNT_PRDT_CD": account["product_code"],
            "PDNO": normalized_symbol,
            "ORD_UNPR": str(max(order_price, 0)),
            "ORD_DVSN": order_division,
            "CMA_EVLU_AMT_ICLD_YN": "N",
            "OVRS_ICLD_YN": "N",
        },
    )
    output = payload.get("output") or {}
    if not isinstance(output, dict):
        raise MarketDataProviderUnavailable("KIS 매수가능조회 응답 형식이 예상과 다릅니다.")

    return normalize_kis_buyable_cash(output, symbol=normalized_symbol)


def fetch_kis_daily_order_executions(
    *,
    start: date | None = None,
    end: date | None = None,
    side: str = "all",
    execution_status: str = "all",
    symbol: str = "",
    max_pages: int = 5,
) -> dict[str, Any]:
    account = get_kis_account_config()
    today = today_kst()
    end_date = end or today
    start_date = start or (end_date - timedelta(days=14))
    if end_date < start_date:
        raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")

    normalized_side = side.strip().lower()
    side_code_by_name = {"all": "00", "sell": "01", "buy": "02"}
    if normalized_side not in side_code_by_name:
        raise ValueError("매수매도 구분은 all, buy, sell만 지원합니다.")

    normalized_execution_status = execution_status.strip().lower()
    execution_code_by_name = {"all": "00", "filled": "01", "unfilled": "02"}
    if normalized_execution_status not in execution_code_by_name:
        raise ValueError("체결 구분은 all, filled, unfilled만 지원합니다.")

    pd_dv = "before" if start_date < today - timedelta(days=90) else "inner"
    if is_kis_paper_trading():
        tr_id = "VTSC9215R" if pd_dv == "before" else "VTTC0081R"
    else:
        tr_id = "CTSC9215R" if pd_dv == "before" else "TTTC0081R"

    orders: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    ctx_area_fk100 = ""
    ctx_area_nk100 = ""
    tr_cont = ""
    safe_max_pages = max(1, min(max_pages, 20))

    for _page in range(safe_max_pages):
        payload, headers = request_kis_open_api(
            method="GET",
            path=KIS_DOMESTIC_DAILY_ORDER_EXECUTION_PATH,
            tr_id=tr_id,
            tr_cont=tr_cont,
            params={
                "CANO": account["account_no"],
                "ACNT_PRDT_CD": account["product_code"],
                "INQR_STRT_DT": start_date.strftime("%Y%m%d"),
                "INQR_END_DT": end_date.strftime("%Y%m%d"),
                "SLL_BUY_DVSN_CD": side_code_by_name[normalized_side],
                "PDNO": normalize_kis_symbol(symbol) if symbol else "",
                "CCLD_DVSN": execution_code_by_name[normalized_execution_status],
                "INQR_DVSN": "00",
                "INQR_DVSN_3": "00",
                "ORD_GNO_BRNO": "",
                "ODNO": "",
                "INQR_DVSN_1": "",
                "CTX_AREA_FK100": ctx_area_fk100,
                "CTX_AREA_NK100": ctx_area_nk100,
                "EXCG_ID_DVSN_CD": "KRX",
            },
        )
        raw_orders = payload.get("output1") or []
        raw_summary = payload.get("output2") or {}
        if isinstance(raw_orders, list):
            orders.extend(normalize_kis_daily_order_execution(row) for row in raw_orders if isinstance(row, dict))
        if isinstance(raw_summary, dict):
            summary = normalize_kis_daily_order_execution_summary(raw_summary)

        ctx_area_fk100 = str(payload.get("ctx_area_fk100") or "")
        ctx_area_nk100 = str(payload.get("ctx_area_nk100") or "")
        response_tr_cont = str(headers.get("tr_cont") or "").strip()
        if response_tr_cont not in {"M", "F"}:
            break
        tr_cont = "N"

    return {
        "provider": KIS_PROVIDER_NAME,
        "environment": get_kis_environment_name(),
        "account_label": account["account_label"],
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "orders": orders,
        "summary": summary,
    }


def submit_kis_domestic_cash_order(
    *,
    side: str,
    symbol: str,
    quantity: int,
    order_type: str = "market",
    price: int = 0,
    exchange_id: str = "KRX",
) -> dict[str, Any]:
    account = get_kis_account_config()
    if quantity <= 0:
        raise ValueError("주문 수량은 1주 이상이어야 합니다.")

    normalized_side = side.strip().lower()
    if normalized_side not in {"buy", "sell"}:
        raise ValueError("주문 구분은 buy 또는 sell만 지원합니다.")

    normalized_order_type = order_type.strip().lower()
    if normalized_order_type not in {"market", "limit"}:
        raise ValueError("주문 방식은 market 또는 limit만 지원합니다.")
    if normalized_order_type == "limit" and price <= 0:
        raise ValueError("지정가 주문은 주문 가격이 필요합니다.")

    if is_kis_paper_trading():
        tr_id = "VTTC0012U" if normalized_side == "buy" else "VTTC0011U"
    else:
        tr_id = "TTTC0012U" if normalized_side == "buy" else "TTTC0011U"

    body = {
        "CANO": account["account_no"],
        "ACNT_PRDT_CD": account["product_code"],
        "PDNO": normalize_kis_symbol(symbol),
        "ORD_DVSN": "01" if normalized_order_type == "market" else "00",
        "ORD_QTY": str(quantity),
        "ORD_UNPR": "0" if normalized_order_type == "market" else str(price),
        "EXCG_ID_DVSN_CD": exchange_id.strip().upper() or "KRX",
    }
    payload, _headers = request_kis_open_api(
        method="POST",
        path=KIS_DOMESTIC_CASH_ORDER_PATH,
        tr_id=tr_id,
        body=body,
        include_hash_key=True,
    )
    output = payload.get("output") or {}
    if not isinstance(output, dict):
        raise MarketDataProviderUnavailable("KIS 현금주문 응답 형식이 예상과 다릅니다.")

    return {
        "provider": KIS_PROVIDER_NAME,
        "environment": get_kis_environment_name(),
        "symbol": body["PDNO"],
        "side": normalized_side,
        "order_type": normalized_order_type,
        "quantity": quantity,
        "price": 0 if normalized_order_type == "market" else price,
        "order_no": str(output.get("ODNO") or ""),
        "order_time": str(output.get("ORD_TMD") or ""),
        "exchange_order_org_no": str(output.get("KRX_FWDG_ORD_ORGNO") or ""),
        "message": payload.get("msg1") or "주문 요청이 접수되었습니다.",
    }


def call_kis_open_api(
    *,
    path: str,
    tr_id: str,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload, _headers = request_kis_open_api(method="GET", path=path, tr_id=tr_id, params=params)
    return payload


def request_kis_open_api(
    *,
    method: str,
    path: str,
    tr_id: str,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    tr_cont: str = "",
    include_hash_key: bool = False,
) -> tuple[dict[str, Any], dict[str, str]]:
    app_key = os.getenv("KIS_APP_KEY", "").strip()
    app_secret = os.getenv("KIS_APP_SECRET", "").strip()

    if not app_key or not app_secret:
        raise MarketDataProviderUnavailable("KIS_APP_KEY와 KIS_APP_SECRET을 설정하세요.")

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {get_kis_access_token()}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
        "custtype": "P",
    }
    if tr_cont:
        headers["tr_cont"] = tr_cont
    if include_hash_key and body:
        headers["hashkey"] = issue_kis_hash_key(body=body, app_key=app_key, app_secret=app_secret)

    try:
        if method.upper() == "POST":
            response = requests.post(
                f"{get_kis_base_url().rstrip('/')}/{path.lstrip('/')}",
                headers=headers,
                json=body or {},
                timeout=20,
            )
        else:
            response = requests.get(
                f"{get_kis_base_url().rstrip('/')}/{path.lstrip('/')}",
                headers=headers,
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

    return payload, {key.lower(): value for key, value in response.headers.items()}


def issue_kis_hash_key(*, body: dict[str, Any], app_key: str, app_secret: str) -> str:
    try:
        response = requests.post(
            f"{get_kis_base_url().rstrip('/')}/uapi/hashkey",
            headers={
                "content-type": "application/json; charset=utf-8",
                "appkey": app_key,
                "appsecret": app_secret,
            },
            json=body,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise MarketDataProviderUnavailable(f"KIS hashkey 발급 실패: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise MarketDataProviderUnavailable("KIS hashkey JSON 응답을 해석하지 못했습니다.") from exc

    if response.status_code != 200:
        message = payload.get("msg1") or payload.get("error_description") or response.text
        raise MarketDataProviderUnavailable(f"KIS hashkey 발급 실패: HTTP {response.status_code} {message}")

    hash_key = str(payload.get("HASH") or "")
    if not hash_key:
        raise MarketDataProviderUnavailable("KIS hashkey 응답에 HASH가 없습니다.")
    return hash_key


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


def normalize_kis_financial_ratio(
    *,
    row: dict[str, Any],
    symbol: str,
    period_type: str,
) -> dict[str, Any] | None:
    fiscal_period = str(row.get("stac_yymm") or "").strip()
    if not fiscal_period:
        return None

    return {
        "provider": KIS_PROVIDER_NAME,
        "symbol": symbol,
        "fiscal_period": fiscal_period,
        "period_type": period_type,
        "revenue_growth": float_from_kis(row.get("grs")),
        "operating_income_growth": float_from_kis(row.get("bsop_prfi_inrt")),
        "net_income_growth": float_from_kis(row.get("ntin_inrt")),
        "roe": float_from_kis(row.get("roe_val")),
        "eps": float_from_kis(row.get("eps")),
        "sps": float_from_kis(row.get("sps")),
        "bps": float_from_kis(row.get("bps")),
        "reserve_ratio": float_from_kis(row.get("rsrv_rate")),
        "debt_ratio": float_from_kis(row.get("lblt_rate")),
    }


def normalize_kis_balance_holding(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(row.get("pdno") or "").strip(),
        "name": str(row.get("prdt_name") or "").strip(),
        "trade_type": str(row.get("trad_dvsn_name") or "").strip(),
        "holding_quantity": int_from_kis(row.get("hldg_qty")) or 0,
        "orderable_quantity": int_from_kis(row.get("ord_psbl_qty")) or 0,
        "average_price": int_from_kis(row.get("pchs_avg_pric")) or 0,
        "purchase_amount": int_from_kis(row.get("pchs_amt")) or 0,
        "current_price": int_from_kis(row.get("prpr")) or 0,
        "evaluation_amount": int_from_kis(row.get("evlu_amt")) or 0,
        "profit_loss_amount": int_from_kis(row.get("evlu_pfls_amt")) or 0,
        "profit_loss_rate": float_from_kis(row.get("evlu_pfls_rt")) or 0,
        "evaluation_earning_rate": float_from_kis(row.get("evlu_erng_rt")) or 0,
        "change_rate": float_from_kis(row.get("fltt_rt")) or 0,
    }


def normalize_kis_balance_summary(row: dict[str, Any]) -> dict[str, Any]:
    purchase_amount = int_from_kis(row.get("pchs_amt_smtl_amt")) or 0
    profit_loss_amount = int_from_kis(row.get("evlu_pfls_smtl_amt")) or 0
    profit_loss_rate = round(profit_loss_amount / purchase_amount * 100, 2) if purchase_amount else 0

    return {
        "deposit_amount": int_from_kis(row.get("dnca_tot_amt")) or 0,
        "next_settlement_amount": int_from_kis(row.get("nxdy_excc_amt")) or 0,
        "purchase_amount": purchase_amount,
        "evaluation_amount": int_from_kis(row.get("evlu_amt_smtl_amt")) or 0,
        "profit_loss_amount": profit_loss_amount,
        "profit_loss_rate": profit_loss_rate,
        "securities_evaluation_amount": int_from_kis(row.get("scts_evlu_amt")) or 0,
        "total_evaluation_amount": int_from_kis(row.get("tot_evlu_amt")) or 0,
        "net_asset_amount": int_from_kis(row.get("nass_amt")) or 0,
        "total_loan_amount": int_from_kis(row.get("tot_loan_amt")) or 0,
        "previous_total_asset_evaluation_amount": int_from_kis(row.get("bfdy_tot_asst_evlu_amt")) or 0,
        "asset_change_amount": int_from_kis(row.get("asst_icdc_amt")) or 0,
        "asset_change_rate": float_from_kis(row.get("asst_icdc_erng_rt")) or 0,
    }


def normalize_kis_buyable_cash(row: dict[str, Any], *, symbol: str) -> dict[str, Any]:
    return {
        "provider": KIS_PROVIDER_NAME,
        "environment": get_kis_environment_name(),
        "symbol": symbol,
        "orderable_cash": int_from_kis(row.get("ord_psbl_cash")) or 0,
        "orderable_substitute": int_from_kis(row.get("ord_psbl_sbst")) or 0,
        "reusable_amount": int_from_kis(row.get("ruse_psbl_amt")) or 0,
        "calculation_unit_price": int_from_kis(row.get("psbl_qty_calc_unpr")) or 0,
        "cash_buy_amount": int_from_kis(row.get("nrcvb_buy_amt")) or 0,
        "cash_buy_quantity": int_from_kis(row.get("nrcvb_buy_qty")) or 0,
        "max_buy_amount": int_from_kis(row.get("max_buy_amt")) or 0,
        "max_buy_quantity": int_from_kis(row.get("max_buy_qty")) or 0,
        "cma_evaluation_amount": int_from_kis(row.get("cma_evlu_amt")) or 0,
    }


def normalize_kis_daily_order_execution(row: dict[str, Any]) -> dict[str, Any]:
    ordered_quantity = int_from_kis(row.get("ord_qty")) or 0
    filled_quantity = int_from_kis(row.get("tot_ccld_qty")) or 0
    remaining_quantity = int_from_kis(row.get("rmn_qty")) or 0
    rejected_quantity = int_from_kis(row.get("rjct_qty")) or 0
    canceled = str(row.get("cncl_yn") or "").strip().upper() == "Y"
    status = "접수"
    if canceled:
        status = "취소"
    elif rejected_quantity > 0:
        status = "거부"
    elif remaining_quantity > 0 and filled_quantity > 0:
        status = "부분체결"
    elif remaining_quantity > 0:
        status = "미체결"
    elif filled_quantity > 0:
        status = "체결"

    return {
        "order_date": format_kis_yyyymmdd(row.get("ord_dt")),
        "order_time": format_kis_hhmmss(row.get("ord_tmd")),
        "order_branch_no": str(row.get("ord_gno_brno") or "").strip(),
        "order_no": str(row.get("odno") or "").strip(),
        "original_order_no": str(row.get("orgn_odno") or "").strip(),
        "symbol": str(row.get("pdno") or "").strip(),
        "name": str(row.get("prdt_name") or "").strip(),
        "side_code": str(row.get("sll_buy_dvsn_cd") or "").strip(),
        "side_name": str(row.get("sll_buy_dvsn_cd_name") or "").strip(),
        "order_type_name": str(row.get("ord_dvsn_name") or "").strip(),
        "order_type_code": str(row.get("ord_dvsn_cd") or "").strip(),
        "ordered_quantity": ordered_quantity,
        "order_price": int_from_kis(row.get("ord_unpr")) or 0,
        "filled_quantity": filled_quantity,
        "average_price": int_from_kis(row.get("avg_prvs")) or 0,
        "filled_amount": int_from_kis(row.get("tot_ccld_amt")) or 0,
        "remaining_quantity": remaining_quantity,
        "rejected_quantity": rejected_quantity,
        "canceled": canceled,
        "status": status,
        "execution_condition": str(row.get("ccld_cndt_name") or "").strip(),
        "exchange_code": str(row.get("excg_dvsn_cd") or row.get("excg_id_dvsn_Cd") or "").strip(),
    }


def normalize_kis_daily_order_execution_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_order_quantity": int_from_kis(row.get("tot_ord_qty")) or 0,
        "total_filled_quantity": int_from_kis(row.get("tot_ccld_qty")) or 0,
        "total_filled_amount": int_from_kis(row.get("tot_ccld_amt")) or 0,
        "estimated_fee_total": int_from_kis(row.get("prsm_tlex_smtl")) or 0,
        "purchase_average_price": int_from_kis(row.get("pchs_avg_pric")) or 0,
    }


def format_kis_yyyymmdd(value: Any) -> str:
    raw = str(value or "").strip()
    if len(raw) != 8:
        return raw
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def format_kis_hhmmss(value: Any) -> str:
    raw = str(value or "").strip()
    if len(raw) != 6:
        return raw
    return f"{raw[:2]}:{raw[2:4]}:{raw[4:6]}"


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
