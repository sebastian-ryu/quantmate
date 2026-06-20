from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import requests

from quantmate_api.config import load_local_env


load_local_env()


class MarketDataProviderUnavailable(RuntimeError):
    pass


SUPPORTED_KRX_MARKETS = {"KOSPI", "KOSDAQ", "KONEX", "ALL"}
KRX_STOCK_BASE_INFO_ENDPOINTS = {
    "KOSPI": "/stk_isu_base_info",
    "KOSDAQ": "/ksq_isu_base_info",
    "KONEX": "/knx_isu_base_info",
}


def has_krx_open_api_auth_key() -> bool:
    return bool(os.getenv("KRX_OPEN_API_AUTH_KEY", "").strip())


def is_krx_open_api_ready() -> bool:
    return has_krx_open_api_auth_key()


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


def default_krx_base_date() -> str:
    candidate = date.today()

    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)

    return candidate.strftime("%Y%m%d")
