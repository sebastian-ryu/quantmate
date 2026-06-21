from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date
from statistics import fmean, pstdev
from typing import Any


CANDIDATE_UNIVERSE: list[dict[str, Any]] = [
    {
        "symbol": "005930",
        "name": "삼성전자",
        "exchange": "KOSPI",
        "sector": "기술",
        "industry": "반도체",
        "market_cap": 2247.7,
        "price": 354000,
        "change_pct": -2.3,
        "per": 14.8,
        "pbr": 1.4,
        "roe": 9.8,
        "revenue_growth": 8.4,
        "foreign_net_buy_5d": 1260,
        "institution_net_buy_5d": 820,
        "supply_score": 86,
        "short_sale_ratio": 3.1,
        "momentum": 82,
    },
    {
        "symbol": "000660",
        "name": "SK하이닉스",
        "exchange": "KOSPI",
        "sector": "기술",
        "industry": "반도체",
        "market_cap": 1957.7,
        "price": 276400,
        "change_pct": 2.9,
        "per": 18.3,
        "pbr": 1.6,
        "roe": 12.2,
        "revenue_growth": 17.2,
        "foreign_net_buy_5d": 2480,
        "institution_net_buy_5d": 1120,
        "supply_score": 91,
        "short_sale_ratio": 4.9,
        "momentum": 78,
    },
    {
        "symbol": "035720",
        "name": "카카오",
        "exchange": "KOSPI",
        "sector": "커뮤니케이션",
        "industry": "인터넷 서비스",
        "market_cap": 23.4,
        "price": 43750,
        "change_pct": 1.2,
        "per": 27.4,
        "pbr": 1.1,
        "roe": 4.5,
        "revenue_growth": 3.1,
        "foreign_net_buy_5d": 180,
        "institution_net_buy_5d": 260,
        "supply_score": 58,
        "short_sale_ratio": 6.2,
        "momentum": 71,
    },
    {
        "symbol": "005380",
        "name": "현대차",
        "exchange": "KOSPI",
        "sector": "소비순환재",
        "industry": "자동차",
        "market_cap": 138.6,
        "price": 613000,
        "change_pct": 2.0,
        "per": 6.2,
        "pbr": 0.8,
        "roe": 12.8,
        "revenue_growth": 9.5,
        "foreign_net_buy_5d": 610,
        "institution_net_buy_5d": 420,
        "supply_score": 77,
        "short_sale_ratio": 2.8,
        "momentum": 74,
    },
    {
        "symbol": "035420",
        "name": "NAVER",
        "exchange": "KOSPI",
        "sector": "커뮤니케이션",
        "industry": "인터넷 서비스",
        "market_cap": 31.2,
        "price": 194500,
        "change_pct": -0.6,
        "per": 22.7,
        "pbr": 1.3,
        "roe": 6.1,
        "revenue_growth": 7.4,
        "foreign_net_buy_5d": 360,
        "institution_net_buy_5d": 190,
        "supply_score": 64,
        "short_sale_ratio": 5.1,
        "momentum": 66,
    },
    {
        "symbol": "247540",
        "name": "에코프로비엠",
        "exchange": "KOSDAQ",
        "sector": "소재",
        "industry": "전지 소재",
        "market_cap": 12.8,
        "price": 132400,
        "change_pct": 4.1,
        "per": 42.5,
        "pbr": 3.8,
        "roe": 8.4,
        "revenue_growth": 19.8,
        "foreign_net_buy_5d": 210,
        "institution_net_buy_5d": 340,
        "supply_score": 69,
        "short_sale_ratio": 7.4,
        "momentum": 83,
    },
    {
        "symbol": "068270",
        "name": "셀트리온",
        "exchange": "KOSPI",
        "sector": "헬스케어",
        "industry": "바이오",
        "market_cap": 41.5,
        "price": 188600,
        "change_pct": 1.5,
        "per": 31.6,
        "pbr": 2.2,
        "roe": 7.6,
        "revenue_growth": 11.9,
        "foreign_net_buy_5d": 520,
        "institution_net_buy_5d": 780,
        "supply_score": 79,
        "short_sale_ratio": 3.9,
        "momentum": 76,
    },
    {
        "symbol": "012450",
        "name": "한화에어로스페이스",
        "exchange": "KOSPI",
        "sector": "산업재",
        "industry": "방산",
        "market_cap": 15.7,
        "price": 315000,
        "change_pct": 3.8,
        "per": 19.4,
        "pbr": 2.5,
        "roe": 14.2,
        "revenue_growth": 24.3,
        "foreign_net_buy_5d": 840,
        "institution_net_buy_5d": 960,
        "supply_score": 88,
        "short_sale_ratio": 2.2,
        "momentum": 89,
    },
    {
        "symbol": "105560",
        "name": "KB금융",
        "exchange": "KOSPI",
        "sector": "금융",
        "industry": "은행",
        "market_cap": 34.1,
        "price": 84600,
        "change_pct": 0.8,
        "per": 5.4,
        "pbr": 0.6,
        "roe": 10.9,
        "revenue_growth": 5.7,
        "foreign_net_buy_5d": 430,
        "institution_net_buy_5d": 510,
        "supply_score": 73,
        "short_sale_ratio": 1.7,
        "momentum": 68,
    },
    {
        "symbol": "051910",
        "name": "LG화학",
        "exchange": "KOSPI",
        "sector": "소재",
        "industry": "화학",
        "market_cap": 25.6,
        "price": 362000,
        "change_pct": -1.1,
        "per": 16.8,
        "pbr": 0.9,
        "roe": 5.6,
        "revenue_growth": 2.4,
        "foreign_net_buy_5d": -120,
        "institution_net_buy_5d": 160,
        "supply_score": 55,
        "short_sale_ratio": 5.7,
        "momentum": 52,
    },
    {
        "symbol": "086790",
        "name": "하나금융지주",
        "exchange": "KOSPI",
        "sector": "금융",
        "industry": "은행",
        "market_cap": 18.9,
        "price": 64200,
        "change_pct": 1.0,
        "per": 4.9,
        "pbr": 0.5,
        "roe": 11.7,
        "revenue_growth": 4.8,
        "foreign_net_buy_5d": 390,
        "institution_net_buy_5d": 350,
        "supply_score": 70,
        "short_sale_ratio": 1.4,
        "momentum": 63,
    },
    {
        "symbol": "034020",
        "name": "두산에너빌리티",
        "exchange": "KOSPI",
        "sector": "산업재",
        "industry": "전력설비",
        "market_cap": 13.8,
        "price": 21500,
        "change_pct": 2.6,
        "per": 28.1,
        "pbr": 1.8,
        "roe": 6.8,
        "revenue_growth": 13.6,
        "foreign_net_buy_5d": 280,
        "institution_net_buy_5d": 230,
        "supply_score": 67,
        "short_sale_ratio": 4.4,
        "momentum": 80,
    },
]

CANDIDATE_METADATA_BY_SYMBOL = {
    str(item["symbol"]): item
    for item in CANDIDATE_UNIVERSE
}

NUMERIC_FORMULA_FIELD_ALIASES = {
    "market_cap_trillion": "market_cap",
    "close": "price",
    "trading_value_억원": "trading_value_krw_100m",
    "avg_volume_20d_만주": "avg_volume_20d_10k",
    "turnover_pct": "turnover_pct",
    "per": "per",
    "pbr": "pbr",
    "psr": "psr",
    "ev_ebitda": "ev_ebitda",
    "fcf_yield": "fcf_yield",
    "fair_value_upside": "fair_value_upside",
    "dividend_yield": "dividend_yield",
    "payout_ratio": "payout_ratio",
    "roe": "roe",
    "roa": "roa",
    "operating_margin": "operating_margin",
    "net_margin": "net_margin",
    "debt_ratio": "debt_ratio",
    "current_ratio": "current_ratio",
    "revenue_growth": "revenue_growth",
    "eps_growth": "eps_growth",
    "operating_income_growth": "operating_income_growth",
    "beta": "beta",
    "momentum_score": "momentum",
    "daily_change_pct": "change_pct",
    "rsi14": "rsi14",
    "volume_surge": "volume_surge",
    "foreign_net_buy_5d_억원": "foreign_net_buy_5d",
    "foreign_net_buy_20d_억원": "foreign_net_buy_20d",
    "institution_net_buy_5d_억원": "institution_net_buy_5d",
    "institution_net_buy_20d_억원": "institution_net_buy_20d",
    "pension_net_buy_20d_억원": "pension_net_buy_20d",
    "program_net_buy_5d_억원": "program_net_buy_5d",
    "foreign_buy_days": "consecutive_foreign_buy_days",
    "short_sale_ratio": "short_sale_ratio",
    "margin_debt_change_5d": "margin_debt_change_5d",
    "supply_score": "supply_score",
    "drawdown_52w": "drawdown_52w",
    "volatility_20d": "volatility_20d",
    "close_vs_ma20_pct": "close_vs_ma20_pct",
    "close_vs_ma60_pct": "close_vs_ma60_pct",
}

TEXT_FORMULA_FIELDS = {"keyword", "exchange", "sector", "industry"}


def build_strategy_candidates(strategy_code: str, limit: int = 12) -> list[dict[str, Any]]:
    rows = []
    for item in CANDIDATE_UNIVERSE:
        candidate = _with_candidate_defaults({**item})
        candidate["strategy_score"] = calculate_strategy_score(strategy_code, candidate)
        candidate["rationale"] = build_rationale(strategy_code, candidate)
        candidate["risk_flags"] = build_risk_flags(candidate)
        rows.append(candidate)

    return sorted(rows, key=lambda item: item["strategy_score"], reverse=True)[:limit]


def build_strategy_candidates_from_daily_prices(
    *,
    strategy_code: str,
    price_rows: list[dict[str, Any]],
    limit: int = 12,
) -> list[dict[str, Any]]:
    rows_by_symbol = _group_price_rows_by_symbol(price_rows)
    candidates: list[dict[str, Any]] = []

    for symbol, rows in rows_by_symbol.items():
        ordered_rows = sorted(rows, key=lambda item: _coerce_date(item["trade_date"]))
        metrics = _build_price_metrics(ordered_rows)
        if metrics is None:
            continue

        metadata = CANDIDATE_METADATA_BY_SYMBOL.get(symbol, {})
        candidate = _build_price_candidate(
            strategy_code=strategy_code,
            symbol=symbol,
            metadata=metadata,
            metrics=metrics,
            latest_row=ordered_rows[-1],
        )
        candidates.append(candidate)

    return sorted(candidates, key=lambda item: item["strategy_score"], reverse=True)[:limit]


def enrich_strategy_candidates_with_quote_snapshots(
    *,
    candidates: list[dict[str, Any]],
    quote_snapshots: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []

    for candidate in candidates:
        snapshot = quote_snapshots.get(str(candidate.get("symbol") or ""))
        if not snapshot:
            enriched.append(candidate)
            continue

        next_candidate = {**candidate}
        snapshot_price = _float_or_none(snapshot.get("price"))
        candidate_price = _float_or_none(next_candidate.get("price"))
        reference_price = candidate_price or snapshot_price
        market_cap_100m = _float_or_none(snapshot.get("market_cap"))
        per = _float_or_none(snapshot.get("per"))
        pbr = _float_or_none(snapshot.get("pbr"))
        turnover_pct = _float_or_none(snapshot.get("turnover_pct"))
        trading_value = _float_or_none(snapshot.get("trading_value"))
        foreign_net_buy_qty = _float_or_none(snapshot.get("foreign_net_buy_qty"))
        program_net_buy_qty = _float_or_none(snapshot.get("program_net_buy_qty"))

        if market_cap_100m and market_cap_100m > 0:
            next_candidate["market_cap"] = round(market_cap_100m / 10_000, 2)
        if per and per > 0:
            next_candidate["per"] = round(per, 2)
        if pbr and pbr > 0:
            next_candidate["pbr"] = round(pbr, 2)
        if turnover_pct is not None:
            next_candidate["turnover_pct"] = round(turnover_pct, 2)
        if trading_value and trading_value > 0:
            next_candidate["trading_value_krw_100m"] = round(trading_value / 100_000_000, 2)
        if foreign_net_buy_qty and reference_price and reference_price > 0:
            next_candidate["foreign_net_buy_5d"] = round(
                foreign_net_buy_qty * reference_price / 100_000_000
            )
        if program_net_buy_qty and reference_price and reference_price > 0:
            next_candidate["program_net_buy_5d"] = round(
                program_net_buy_qty * reference_price / 100_000_000
            )

        next_candidate["rationale"] = [
            *next_candidate.get("rationale", []),
            "KIS 현재가 스냅샷으로 시총/PER/PBR 보강",
        ]
        if foreign_net_buy_qty:
            next_candidate["risk_flags"] = [
                *next_candidate.get("risk_flags", []),
                "외국인 순매수는 KIS 현재가 단일 스냅샷 기준",
            ]
        enriched.append(next_candidate)

    return sorted(enriched, key=lambda item: item["strategy_score"], reverse=True)


def enrich_strategy_candidates_with_supply_flows(
    *,
    candidates: list[dict[str, Any]],
    supply_flows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []

    for candidate in candidates:
        flow = supply_flows.get(str(candidate.get("symbol") or ""))
        if not flow:
            enriched.append(candidate)
            continue

        next_candidate = {**candidate}
        for key in (
            "foreign_net_buy_5d",
            "institution_net_buy_5d",
            "foreign_net_buy_20d",
            "institution_net_buy_20d",
            "pension_net_buy_20d",
            "consecutive_foreign_buy_days",
        ):
            next_candidate[key] = flow.get(key, next_candidate.get(key, 0))

        flow_score = _float_or_zero(flow.get("supply_score"))
        if flow_score > 0:
            next_candidate["supply_score"] = round(max(_float_or_zero(next_candidate.get("supply_score")), flow_score))

        next_candidate["rationale"] = [
            *next_candidate.get("rationale", []),
            "KIS 투자자별 매매동향으로 수급 보강",
        ]
        enriched.append(next_candidate)

    return sorted(enriched, key=lambda item: item["strategy_score"], reverse=True)


def enrich_strategy_candidates_with_risk_indicators(
    *,
    candidates: list[dict[str, Any]],
    risk_indicators: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []

    for candidate in candidates:
        indicator = risk_indicators.get(str(candidate.get("symbol") or ""))
        if not indicator:
            enriched.append(candidate)
            continue

        next_candidate = {**candidate}
        short_sale_ratio = _float_or_none(indicator.get("short_sale_ratio"))
        margin_debt_change_5d = _float_or_none(indicator.get("margin_debt_change_5d"))

        if short_sale_ratio is not None:
            next_candidate["short_sale_ratio"] = round(short_sale_ratio, 2)
        if margin_debt_change_5d is not None:
            next_candidate["margin_debt_change_5d"] = round(margin_debt_change_5d, 2)

        next_candidate["rationale"] = [
            *next_candidate.get("rationale", []),
            "KIS 공매도/신용잔고 지표로 리스크 보강",
        ]
        risk_flags = [*next_candidate.get("risk_flags", [])]
        if short_sale_ratio is not None and short_sale_ratio >= 8:
            risk_flags.append("공매도 비중 높음")
        if margin_debt_change_5d is not None and margin_debt_change_5d >= 15:
            risk_flags.append("신용잔고 단기 증가")
        next_candidate["risk_flags"] = risk_flags
        enriched.append(next_candidate)

    return sorted(enriched, key=lambda item: item["strategy_score"], reverse=True)


def _with_candidate_defaults(item: dict[str, Any]) -> dict[str, Any]:
    item.setdefault("psr", _derived_psr(item))
    item.setdefault("ev_ebitda", _derived_ev_ebitda(item))
    item.setdefault("fcf_yield", _derived_fcf_yield(item))
    item.setdefault("dividend_yield", _derived_dividend_yield(item))
    item.setdefault("payout_ratio", 25.0)
    item.setdefault("roa", _float_or_zero(item.get("roe")) * 0.55)
    item.setdefault("operating_margin", _derived_operating_margin(item))
    item.setdefault("net_margin", _float_or_zero(item.get("roe")) * 0.7)
    item.setdefault("debt_ratio", 85.0)
    item.setdefault("current_ratio", 150.0)
    item.setdefault("eps_growth", _float_or_zero(item.get("revenue_growth")) * 1.2)
    item.setdefault("operating_income_growth", _float_or_zero(item.get("revenue_growth")) * 1.4)
    item.setdefault("beta", 1.0)
    item.setdefault("trading_value_krw_100m", 0.0)
    item.setdefault("avg_volume_20d_10k", 0.0)
    item.setdefault("turnover_pct", 0.0)
    item.setdefault("volatility_20d", 0.0)
    item.setdefault("drawdown_52w", 0.0)
    item.setdefault("rsi14", 50.0)
    item.setdefault("close_vs_ma20_pct", 0.0)
    item.setdefault("close_vs_ma60_pct", 0.0)
    item.setdefault("volume_surge", 1.0)
    item.setdefault("fair_value_upside", 0.0)
    item.setdefault("foreign_net_buy_20d", 0)
    item.setdefault("institution_net_buy_20d", 0)
    item.setdefault("pension_net_buy_20d", 0)
    item.setdefault("program_net_buy_5d", 0)
    item.setdefault("consecutive_foreign_buy_days", 0)
    item.setdefault("margin_debt_change_5d", 0.0)
    return item


def apply_user_strategy_formula(
    *,
    candidates: list[dict[str, Any]],
    formula: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    normalized_formula = formula.strip()
    if not normalized_formula or normalized_formula.startswith("필터를 선택하면"):
        return candidates, []

    conditions = [condition.strip() for condition in normalized_formula.split(" AND ") if condition.strip()]
    unsupported_conditions: list[str] = []
    filtered_candidates: list[dict[str, Any]] = []

    for candidate in candidates:
        passed = True

        for condition in conditions:
            condition_passed, supported = _evaluate_formula_condition(candidate, condition)

            if not supported:
                if condition not in unsupported_conditions:
                    unsupported_conditions.append(condition)
                continue

            if not condition_passed:
                passed = False
                break

        if passed:
            filtered_candidates.append(candidate)

    if unsupported_conditions:
        filtered_candidates = [
            {
                **candidate,
                "risk_flags": [
                    *candidate.get("risk_flags", []),
                    "검색식 일부 조건 미연동",
                ],
                "rationale": [
                    *candidate.get("rationale", []),
                    f"미연동 조건 {len(unsupported_conditions)}개는 제외 없이 표시",
                ],
            }
            for candidate in filtered_candidates
        ]

    return filtered_candidates, unsupported_conditions


def _evaluate_formula_condition(candidate: dict[str, Any], condition: str) -> tuple[bool, bool]:
    if condition == "close > ma20":
        return _numeric_value(candidate, "close_vs_ma20_pct") > 0, True
    if condition == "close > ma60":
        return _numeric_value(candidate, "close_vs_ma60_pct") > 0, True

    abs_match = re.fullmatch(
        r"abs\((?P<field>[\w가-힣_]+)\)\s*(?P<operator><=|>=|<|>)\s*(?P<value>-?\d+(?:\.\d+)?)",
        condition,
    )
    if abs_match:
        value = abs(_numeric_value(candidate, abs_match.group("field")))
        return _compare_numeric(value, abs_match.group("operator"), float(abs_match.group("value"))), True

    contains_match = re.fullmatch(r'(?P<field>[\w가-힣_]+)\s+contains\s+"(?P<value>[^"]*)"', condition)
    if contains_match:
        field = contains_match.group("field")
        value = contains_match.group("value").strip().lower()
        return _evaluate_contains_condition(candidate, field, value)

    text_match = re.fullmatch(r'(?P<field>[\w가-힣_]+)\s*==\s*"(?P<value>[^"]*)"', condition)
    if text_match:
        field = text_match.group("field")
        value = text_match.group("value").strip().lower()
        if field not in TEXT_FORMULA_FIELDS:
            return True, False
        return str(candidate.get(field, "")).strip().lower() == value, True

    numeric_match = re.fullmatch(
        r"(?P<field>[\w가-힣_]+)\s*(?P<operator>>=|<=|>|<|==)\s*(?P<value>-?\d+(?:\.\d+)?)",
        condition,
    )
    if numeric_match:
        field = numeric_match.group("field")
        if field not in NUMERIC_FORMULA_FIELD_ALIASES:
            return True, False
        value = _numeric_value(candidate, NUMERIC_FORMULA_FIELD_ALIASES[field])
        return _compare_numeric(value, numeric_match.group("operator"), float(numeric_match.group("value"))), True

    return True, False


def _evaluate_contains_condition(
    candidate: dict[str, Any],
    field: str,
    value: str,
) -> tuple[bool, bool]:
    if field == "keyword":
        text = " ".join(
            str(candidate.get(key, ""))
            for key in ("symbol", "name", "exchange", "sector", "industry")
        ).lower()
        return value in text, True

    if field not in TEXT_FORMULA_FIELDS:
        return True, False

    return value in str(candidate.get(field, "")).lower(), True


def _numeric_value(candidate: dict[str, Any], field: str) -> float:
    value = candidate.get(field)
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _compare_numeric(value: float, operator: str, expected: float) -> bool:
    if operator == ">=":
        return value >= expected
    if operator == "<=":
        return value <= expected
    if operator == ">":
        return value > expected
    if operator == "<":
        return value < expected
    if operator == "==":
        return value == expected
    return False


def _group_price_rows_by_symbol(price_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    rows_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in price_rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol:
            rows_by_symbol[symbol].append(row)

    return rows_by_symbol


def _build_price_metrics(rows: list[dict[str, Any]]) -> dict[str, float] | None:
    if len(rows) < 2:
        return None

    closes = [_float_or_zero(row.get("close_price", row.get("close"))) for row in rows]
    volumes = [_float_or_zero(row.get("volume")) for row in rows]

    if len(closes) < 2 or closes[-1] <= 0:
        return None

    latest_close = closes[-1]
    previous_close = closes[-2] if len(closes) >= 2 and closes[-2] > 0 else latest_close
    change_pct = _pct_change(previous_close, latest_close)
    ma20 = fmean(closes[-20:])
    ma60 = fmean(closes[-60:]) if len(closes) >= 60 else ma20
    high_252 = max(closes[-252:]) if len(closes) >= 252 else max(closes)
    low_252 = min(closes[-252:]) if len(closes) >= 252 else min(closes)
    return_21 = _return_over_days(closes, 21)
    return_63 = _return_over_days(closes, 63)
    return_126 = _return_over_days(closes, 126)
    return_252 = _return_over_days(closes, 252)
    volatility_60 = _annualized_volatility(closes[-61:])
    volatility_20 = _annualized_volatility(closes[-21:])
    mdd_252 = _max_drawdown(closes[-252:] if len(closes) >= 252 else closes)
    rsi14 = _rsi(closes[-15:])
    avg_volume_20 = fmean(volumes[-20:]) if volumes[-20:] else 0
    avg_volume_60 = fmean(volumes[-60:]) if len(volumes) >= 60 else avg_volume_20
    volume_ratio = volumes[-1] / avg_volume_20 if avg_volume_20 > 0 else 1.0
    volume_trend = avg_volume_20 / avg_volume_60 if avg_volume_60 > 0 else 1.0
    positive_days_20 = sum(
        1
        for index in range(max(1, len(closes) - 20), len(closes))
        if closes[index] > closes[index - 1]
    )
    breakout_20 = 1.0 if len(closes) >= 21 and latest_close >= max(closes[-21:-1]) else 0.0
    breakout_55 = 1.0 if len(closes) >= 56 and latest_close >= max(closes[-56:-1]) else 0.0
    high_proximity = latest_close / high_252 if high_252 > 0 else 0.0
    drawup_from_low = latest_close / low_252 - 1 if low_252 > 0 else 0.0
    trading_value = _float_or_zero(rows[-1].get("trading_value"))
    if trading_value <= 0:
        trading_value = latest_close * volumes[-1]

    momentum_score = clamp_score(
        50
        + return_21 * 0.35
        + return_63 * 0.32
        + return_126 * 0.2
        + return_252 * 0.12
    )
    trend_score = clamp_score(
        35
        + (latest_close / ma20 - 1) * 180
        + (latest_close / ma60 - 1) * 140
        + (ma20 / ma60 - 1) * 120
    )
    liquidity_score = clamp_score(45 + min(volume_ratio, 3.0) * 12 + min(volume_trend, 2.5) * 8)
    high_score = clamp_score(high_proximity * 100)
    low_volatility_score = clamp_score(100 - volatility_60 * 2.5)
    mdd_score = clamp_score(100 + mdd_252 * 2)
    breakout_score = clamp_score(45 + breakout_20 * 22 + breakout_55 * 25 + min(volume_ratio, 3.0) * 5)
    accumulation_score = clamp_score(
        35
        + positive_days_20 * 2.2
        + min(volume_trend, 2.5) * 10
        + max(return_21, 0) * 0.45
        + max(drawup_from_low * 100, 0) * 0.05
    )

    return {
        "latest_close": latest_close,
        "change_pct": change_pct,
        "return_21": return_21,
        "return_63": return_63,
        "return_126": return_126,
        "return_252": return_252,
        "ma20": ma20,
        "ma60": ma60,
        "high_proximity": high_proximity,
        "volume_ratio": volume_ratio,
        "volume_trend": volume_trend,
        "avg_volume_20": avg_volume_20,
        "trading_value": trading_value,
        "volatility_60": volatility_60,
        "volatility_20": volatility_20,
        "mdd_252": mdd_252,
        "rsi14": rsi14,
        "positive_days_20": float(positive_days_20),
        "breakout_score": float(breakout_score),
        "momentum_score": float(momentum_score),
        "trend_score": float(trend_score),
        "liquidity_score": float(liquidity_score),
        "high_score": float(high_score),
        "low_volatility_score": float(low_volatility_score),
        "mdd_score": float(mdd_score),
        "accumulation_score": float(accumulation_score),
    }


def _build_price_candidate(
    *,
    strategy_code: str,
    symbol: str,
    metadata: dict[str, Any],
    metrics: dict[str, float],
    latest_row: dict[str, Any],
) -> dict[str, Any]:
    price = round(metrics["latest_close"])
    supply_score = clamp_score(
        metrics["liquidity_score"] * 0.45
        + metrics["accumulation_score"] * 0.45
        + max(metrics["return_21"], 0) * 0.2
    )
    item = {
        "symbol": symbol,
        "name": str(latest_row.get("name") or metadata.get("name") or symbol),
        "exchange": str(latest_row.get("exchange") or metadata.get("exchange") or "KR"),
        "sector": str(metadata.get("sector") or "미분류"),
        "industry": str(metadata.get("industry") or "미분류"),
        "market_cap": float(metadata.get("market_cap") or 0),
        "price": price,
        "change_pct": round(metrics["change_pct"], 1),
        "per": float(metadata.get("per") or 0),
        "pbr": float(metadata.get("pbr") or 0),
        "psr": _metadata_float(metadata, "psr", _derived_psr(metadata)),
        "ev_ebitda": _metadata_float(metadata, "ev_ebitda", _derived_ev_ebitda(metadata)),
        "fcf_yield": _metadata_float(metadata, "fcf_yield", _derived_fcf_yield(metadata)),
        "dividend_yield": _metadata_float(metadata, "dividend_yield", _derived_dividend_yield(metadata)),
        "payout_ratio": _metadata_float(metadata, "payout_ratio", 25.0),
        "roe": float(metadata.get("roe") or 0),
        "roa": _metadata_float(metadata, "roa", float(metadata.get("roe") or 0) * 0.55),
        "operating_margin": _metadata_float(metadata, "operating_margin", _derived_operating_margin(metadata)),
        "net_margin": _metadata_float(metadata, "net_margin", float(metadata.get("roe") or 0) * 0.7),
        "debt_ratio": _metadata_float(metadata, "debt_ratio", 85.0),
        "current_ratio": _metadata_float(metadata, "current_ratio", 150.0),
        "revenue_growth": float(metadata.get("revenue_growth") or 0),
        "eps_growth": _metadata_float(metadata, "eps_growth", float(metadata.get("revenue_growth") or 0) * 1.2),
        "operating_income_growth": _metadata_float(
            metadata,
            "operating_income_growth",
            float(metadata.get("revenue_growth") or 0) * 1.4,
        ),
        "beta": _metadata_float(metadata, "beta", 1.0),
        "foreign_net_buy_5d": 0,
        "foreign_net_buy_20d": 0,
        "institution_net_buy_5d": 0,
        "institution_net_buy_20d": 0,
        "pension_net_buy_20d": 0,
        "program_net_buy_5d": 0,
        "consecutive_foreign_buy_days": 0,
        "supply_score": supply_score,
        "short_sale_ratio": 0.0,
        "margin_debt_change_5d": 0.0,
        "momentum": clamp_score(metrics["momentum_score"]),
        "trading_value_krw_100m": round(metrics["trading_value"] / 100_000_000, 2),
        "avg_volume_20d_10k": round(metrics["avg_volume_20"] / 10_000, 2),
        "turnover_pct": 0.0,
        "volume_surge": round(metrics["volume_ratio"], 2),
        "drawdown_52w": round(metrics["mdd_252"], 1),
        "volatility_20d": round(metrics["volatility_20"], 1),
        "rsi14": round(metrics["rsi14"], 1),
        "close_vs_ma20_pct": round((metrics["latest_close"] / metrics["ma20"] - 1) * 100, 1)
        if metrics["ma20"] > 0
        else 0.0,
        "close_vs_ma60_pct": round((metrics["latest_close"] / metrics["ma60"] - 1) * 100, 1)
        if metrics["ma60"] > 0
        else 0.0,
        "fair_value_upside": _metadata_float(metadata, "fair_value_upside", 0.0),
    }
    item["strategy_score"] = calculate_price_strategy_score(strategy_code, item, metrics)
    item["rationale"] = build_price_rationale(strategy_code, item, metrics)
    item["risk_flags"] = build_price_risk_flags(strategy_code, item, metrics)
    return item


def calculate_price_strategy_score(
    strategy_code: str,
    item: dict[str, Any],
    metrics: dict[str, float],
) -> int:
    if strategy_code == "relative-momentum-swing":
        overheat_penalty = max(metrics["return_21"] - 25, 0) * 0.45
        return clamp_score(
            metrics["momentum_score"] * 0.5
            + metrics["trend_score"] * 0.28
            + metrics["liquidity_score"] * 0.16
            + metrics["high_score"] * 0.1
            - overheat_penalty
        )

    if strategy_code == "value-quality-factor":
        value_quality = (
            item["roe"] * 2.1
            + (30 - min(item["per"] or 30, 30)) * 1.2
            + (4 - min(item["pbr"] or 4, 4)) * 6
            + max(item["revenue_growth"], 0) * 0.5
        )
        return clamp_score(value_quality * 0.72 + metrics["trend_score"] * 0.18 + metrics["mdd_score"] * 0.1)

    if strategy_code == "growth-breakout-leader":
        return clamp_score(
            metrics["high_score"] * 0.32
            + metrics["breakout_score"] * 0.25
            + metrics["momentum_score"] * 0.23
            + metrics["liquidity_score"] * 0.12
            + max(item["revenue_growth"], 0) * 0.35
        )

    if strategy_code == "trend-breakout":
        volatility_penalty = max(metrics["volatility_60"] - 45, 0) * 0.35
        return clamp_score(
            metrics["breakout_score"] * 0.4
            + metrics["trend_score"] * 0.28
            + metrics["liquidity_score"] * 0.18
            + metrics["momentum_score"] * 0.18
            - volatility_penalty
        )

    if strategy_code == "supply-demand-accumulation":
        return clamp_score(
            metrics["accumulation_score"] * 0.45
            + metrics["liquidity_score"] * 0.24
            + metrics["trend_score"] * 0.2
            + max(metrics["return_21"], 0) * 0.18
        )

    if strategy_code == "low-volatility-defensive":
        return clamp_score(
            metrics["low_volatility_score"] * 0.42
            + metrics["mdd_score"] * 0.28
            + metrics["trend_score"] * 0.16
            + item["roe"] * 0.9
            + (20 - min(item["per"] or 20, 20)) * 0.5
        )

    return clamp_score(
        metrics["momentum_score"] * 0.35
        + metrics["trend_score"] * 0.3
        + metrics["liquidity_score"] * 0.2
        + metrics["mdd_score"] * 0.15
    )


def build_price_rationale(
    strategy_code: str,
    item: dict[str, Any],
    metrics: dict[str, float],
) -> list[str]:
    if strategy_code == "relative-momentum-swing":
        return [
            f"3개월 수익률 {format_signed_percent(metrics['return_63'])}",
            f"20/60일 추세 점수 {round(metrics['trend_score'])}점",
            f"거래량 배율 {metrics['volume_ratio']:.1f}배",
        ]

    if strategy_code == "value-quality-factor":
        return [
            f"PER {item['per']}배 / PBR {item['pbr']}배",
            f"ROE {item['roe']}%",
            f"가격 추세 점수 {round(metrics['trend_score'])}점",
        ]

    if strategy_code == "growth-breakout-leader":
        return [
            f"52주 고점 근접도 {metrics['high_proximity'] * 100:.1f}%",
            f"돌파 점수 {round(metrics['breakout_score'])}점",
            f"6개월 수익률 {format_signed_percent(metrics['return_126'])}",
        ]

    if strategy_code == "trend-breakout":
        return [
            f"20/55일 돌파 점수 {round(metrics['breakout_score'])}점",
            f"거래량 배율 {metrics['volume_ratio']:.1f}배",
            f"60일 변동성 {metrics['volatility_60']:.1f}%",
        ]

    if strategy_code == "supply-demand-accumulation":
        return [
            f"거래량 누적 대체점수 {round(metrics['accumulation_score'])}점",
            f"상승일수 {round(metrics['positive_days_20'])}/20일",
            "실제 투자자별 수급은 KRX/KIS 수급 데이터 연결 후 반영",
        ]

    if strategy_code == "low-volatility-defensive":
        return [
            f"60일 변동성 {metrics['volatility_60']:.1f}%",
            f"최근 MDD {format_signed_percent(metrics['mdd_252'])}",
            f"저변동성 점수 {round(metrics['low_volatility_score'])}점",
        ]

    return [
        f"모멘텀 {round(metrics['momentum_score'])}점",
        f"추세 {round(metrics['trend_score'])}점",
        f"거래량 배율 {metrics['volume_ratio']:.1f}배",
    ]


def build_price_risk_flags(
    strategy_code: str,
    item: dict[str, Any],
    metrics: dict[str, float],
) -> list[str]:
    flags: list[str] = []

    if metrics["return_21"] >= 25:
        flags.append("단기 급등")
    if metrics["volatility_60"] >= 55:
        flags.append("변동성 높음")
    if metrics["mdd_252"] <= -30:
        flags.append("최근 낙폭 큼")
    if metrics["volume_ratio"] < 0.7:
        flags.append("거래량 둔화")
    if metrics["trend_score"] < 45:
        flags.append("추세 약함")
    if strategy_code == "supply-demand-accumulation":
        flags.append("투자자별 실제 수급 미반영")
    if strategy_code == "value-quality-factor" and not item["roe"]:
        flags.append("재무지표 미연동")

    return flags


def calculate_strategy_score(strategy_code: str, item: dict[str, Any]) -> int:
    if strategy_code == "relative-momentum-swing":
        return clamp_score(
            item["momentum"] * 0.5
            + item["supply_score"] * 0.18
            + max(item["change_pct"], 0) * 4
            + item["revenue_growth"] * 0.7
            - item["short_sale_ratio"] * 0.8
        )

    if strategy_code == "value-quality-factor":
        return clamp_score(
            item["roe"] * 2.4
            + (30 - min(item["per"], 30)) * 1.35
            + (4 - min(item["pbr"], 4)) * 7
            + max(item["revenue_growth"], 0) * 0.7
        )

    if strategy_code == "growth-breakout-leader":
        return clamp_score(
            item["revenue_growth"] * 1.5
            + item["momentum"] * 0.35
            + max(item["change_pct"], 0) * 5
            + item["supply_score"] * 0.2
            - max(item["per"] - 35, 0) * 0.5
        )

    if strategy_code == "trend-breakout":
        return clamp_score(
            item["momentum"] * 0.48
            + max(item["change_pct"], 0) * 6
            + item["supply_score"] * 0.25
            - max(item["short_sale_ratio"] - 5, 0) * 1.2
        )

    if strategy_code == "supply-demand-accumulation":
        return clamp_score(
            item["supply_score"] * 0.55
            + max(item["foreign_net_buy_5d"], 0) / 70
            + max(item["institution_net_buy_5d"], 0) / 80
            + item["momentum"] * 0.15
        )

    if strategy_code == "low-volatility-defensive":
        return clamp_score(
            38
            - abs(item["change_pct"]) * 4
            - item["short_sale_ratio"] * 2
            + item["roe"] * 2
            + (22 - min(item["per"], 22)) * 0.9
            + (3 - min(item["pbr"], 3)) * 6
            + item["supply_score"] * 0.12
        )

    return clamp_score(
        item["momentum"] * 0.35
        + item["supply_score"] * 0.35
        + item["roe"] * 1.2
        + max(item["revenue_growth"], 0) * 0.8
    )


def build_rationale(strategy_code: str, item: dict[str, Any]) -> list[str]:
    if strategy_code == "relative-momentum-swing":
        return [
            f"모멘텀 {item['momentum']}점",
            f"수급 점수 {item['supply_score']}점",
            f"매출 성장률 {item['revenue_growth']}%",
        ]

    if strategy_code == "value-quality-factor":
        return [
            f"PER {item['per']}배 / PBR {item['pbr']}배",
            f"ROE {item['roe']}%",
            f"매출 성장률 {item['revenue_growth']}%",
        ]

    if strategy_code == "growth-breakout-leader":
        return [
            f"매출 성장률 {item['revenue_growth']}%",
            f"모멘텀 {item['momentum']}점",
            f"당일 등락률 {format_signed_percent(item['change_pct'])}",
        ]

    if strategy_code == "trend-breakout":
        return [
            f"모멘텀 {item['momentum']}점",
            f"당일 등락률 {format_signed_percent(item['change_pct'])}",
            f"거래/수급 점수 {item['supply_score']}점",
        ]

    if strategy_code == "supply-demand-accumulation":
        return [
            f"외국인 5일 {format_signed_amount(item['foreign_net_buy_5d'])}",
            f"기관 5일 {format_signed_amount(item['institution_net_buy_5d'])}",
            f"수급 점수 {item['supply_score']}점",
        ]

    if strategy_code == "low-volatility-defensive":
        return [
            f"당일 변동 {format_signed_percent(item['change_pct'])}",
            f"공매도 비율 {item['short_sale_ratio']}%",
            f"ROE {item['roe']}%",
        ]

    return [
        f"모멘텀 {item['momentum']}점",
        f"수급 점수 {item['supply_score']}점",
        f"ROE {item['roe']}%",
    ]


def build_risk_flags(item: dict[str, Any]) -> list[str]:
    flags: list[str] = []

    if item["short_sale_ratio"] >= 6:
        flags.append("공매도 비율 높음")
    if item["per"] >= 35:
        flags.append("고PER 구간")
    if item["change_pct"] >= 4:
        flags.append("단기 급등")
    if item["foreign_net_buy_5d"] < 0:
        flags.append("외국인 순매도")
    if item["roe"] < 6:
        flags.append("수익성 낮음")
    if item["supply_score"] < 60:
        flags.append("수급 점수 낮음")

    return flags


def clamp_score(score: float) -> int:
    return max(0, min(100, round(score)))


def _coerce_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("거래일 형식이 올바르지 않습니다.")


def _float_or_zero(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(numeric) or math.isinf(numeric):
        return 0.0
    return numeric


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _metadata_float(metadata: dict[str, Any], key: str, default: float) -> float:
    value = _float_or_none(metadata.get(key))
    if value is None:
        return round(default, 2)
    return round(value, 2)


def _derived_psr(metadata: dict[str, Any]) -> float:
    per = _float_or_none(metadata.get("per")) or 0
    pbr = _float_or_none(metadata.get("pbr")) or 0
    return max(0.2, min(8.0, per * 0.08 + pbr * 0.7))


def _derived_ev_ebitda(metadata: dict[str, Any]) -> float:
    per = _float_or_none(metadata.get("per")) or 12
    return max(2.0, min(25.0, per * 0.55))


def _derived_fcf_yield(metadata: dict[str, Any]) -> float:
    per = _float_or_none(metadata.get("per")) or 20
    roe = _float_or_none(metadata.get("roe")) or 0
    return max(-2.0, min(12.0, roe * 0.22 + (20 - min(per, 20)) * 0.18))


def _derived_dividend_yield(metadata: dict[str, Any]) -> float:
    sector = str(metadata.get("sector") or "")
    if sector == "금융":
        return 4.0
    if sector in {"산업재", "소비순환재"}:
        return 1.8
    return 0.7


def _derived_operating_margin(metadata: dict[str, Any]) -> float:
    roe = _float_or_none(metadata.get("roe")) or 0
    growth = _float_or_none(metadata.get("revenue_growth")) or 0
    return max(1.0, min(30.0, roe * 0.9 + max(growth, 0) * 0.2))


def _rsi(closes: list[float]) -> float:
    if len(closes) < 2:
        return 50.0

    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(closes)):
        change = closes[index] - closes[index - 1]
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))

    average_gain = fmean(gains) if gains else 0
    average_loss = fmean(losses) if losses else 0
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0

    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def _pct_change(start: float, end: float) -> float:
    if start <= 0:
        return 0.0
    return (end / start - 1) * 100


def _return_over_days(closes: list[float], days: int) -> float:
    if len(closes) <= days:
        return _pct_change(closes[0], closes[-1])
    return _pct_change(closes[-days - 1], closes[-1])


def _annualized_volatility(closes: list[float]) -> float:
    returns = [
        closes[index] / closes[index - 1] - 1
        for index in range(1, len(closes))
        if closes[index - 1] > 0
    ]
    if len(returns) < 2:
        return 0.0
    return pstdev(returns) * math.sqrt(252) * 100


def _max_drawdown(closes: list[float]) -> float:
    peak = 0.0
    max_drawdown = 0.0

    for close in closes:
        peak = max(peak, close)
        if peak > 0:
            drawdown = (close / peak - 1) * 100
            max_drawdown = min(max_drawdown, drawdown)

    return max_drawdown


def format_signed_percent(value: float) -> str:
    return f"{value:+.1f}%"


def format_signed_amount(value: float) -> str:
    return f"{value:+,.0f}억"
