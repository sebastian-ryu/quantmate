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
    "dividend_growth": "dividend_growth",
    "dividend_streak_years": "dividend_streak_years",
    "dividend_stability_score": "dividend_stability_score",
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
KOREAN_NUMERIC_FORMULA_FIELD_ALIASES = {
    "시가총액": "market_cap",
    "현재가": "price",
    "종가": "price",
    "거래대금": "trading_value_krw_100m",
    "20일평균거래량": "avg_volume_20d_10k",
    "회전율": "turnover_pct",
    "per": "per",
    "pbr": "pbr",
    "psr": "psr",
    "ev/ebitda": "ev_ebitda",
    "fcfyield": "fcf_yield",
    "목표가괴리": "fair_value_upside",
    "배당수익률": "dividend_yield",
    "배당성향": "payout_ratio",
    "배당성장률": "dividend_growth",
    "배당성장": "dividend_growth",
    "연속배당": "dividend_streak_years",
    "배당안정성점수": "dividend_stability_score",
    "roe": "roe",
    "roa": "roa",
    "영업이익률": "operating_margin",
    "순이익률": "net_margin",
    "부채비율": "debt_ratio",
    "유동비율": "current_ratio",
    "매출성장률": "revenue_growth",
    "eps성장률": "eps_growth",
    "영업이익성장률": "operating_income_growth",
    "베타": "beta",
    "20일변동성": "volatility_20d",
    "52주낙폭": "drawdown_52w",
    "모멘텀": "momentum",
    "모멘텀점수": "momentum",
    "당일등락률": "change_pct",
    "일일변동률": "change_pct",
    "rsi": "rsi14",
    "rsi14": "rsi14",
    "거래량급증배수": "volume_surge",
    "외국인5일순매수": "foreign_net_buy_5d",
    "외국인20일순매수": "foreign_net_buy_20d",
    "기관5일순매수": "institution_net_buy_5d",
    "기관20일순매수": "institution_net_buy_20d",
    "연기금20일순매수": "pension_net_buy_20d",
    "프로그램5일순매수": "program_net_buy_5d",
    "외국인연속순매수일": "consecutive_foreign_buy_days",
    "공매도비중": "short_sale_ratio",
    "신용잔고5일변화": "margin_debt_change_5d",
    "수급점수": "supply_score",
}


def build_strategy_candidates(strategy_code: str, limit: int = 12) -> list[dict[str, Any]]:
    rows = []
    for item in CANDIDATE_UNIVERSE:
        candidate = _with_candidate_defaults({**item})
        candidate["strategy_score"] = calculate_strategy_score(strategy_code, candidate)
        candidate["rationale"] = build_rationale(strategy_code, candidate)
        candidate["risk_flags"] = build_risk_flags(candidate)
        rows.append(candidate)

    return apply_candidate_quality_filters(strategy_code, rows, limit=limit)


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

    return apply_candidate_quality_filters(strategy_code, candidates, limit=limit)


def apply_candidate_quality_filters(
    strategy_code: str,
    candidates: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if not candidates:
        return []

    safe_limit = max(1, min(limit, 100))
    marked_candidates = [_with_quality_filter_flags(strategy_code, candidate) for candidate in candidates]
    sorted_candidates = sorted(marked_candidates, key=lambda item: item["strategy_score"], reverse=True)
    hard_allowed = [candidate for candidate in sorted_candidates if not _fails_hard_exclusion(candidate)]
    preferred = [
        candidate
        for candidate in hard_allowed
        if not _fails_liquidity_filter(candidate) and not _fails_risk_exclusion_filter(candidate)
    ]

    minimum_preferred_count = min(safe_limit, 10)
    if len(preferred) >= minimum_preferred_count:
        return preferred[:safe_limit]

    return hard_allowed[:safe_limit]


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
        next_candidate["risk_flags"] = [
            flag for flag in next_candidate.get("risk_flags", []) if flag != "투자자별 실제 수급 미반영"
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


def enrich_strategy_candidates_with_fundamentals(
    *,
    strategy_code: str,
    candidates: list[dict[str, Any]],
    fundamentals: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []

    for candidate in candidates:
        fundamental = fundamentals.get(str(candidate.get("symbol") or ""))
        if not fundamental:
            enriched.append(candidate)
            continue

        next_candidate = {**candidate}
        numeric_fields = (
            ("revenue_growth", "revenue_growth"),
            ("operating_income_growth", "operating_income_growth"),
            ("eps_growth", "net_income_growth"),
            ("roe", "roe"),
            ("debt_ratio", "debt_ratio"),
        )
        for candidate_key, fundamental_key in numeric_fields:
            value = _float_or_none(fundamental.get(fundamental_key))
            if value is not None:
                next_candidate[candidate_key] = round(value, 2)

        price = _float_or_none(next_candidate.get("price")) or 0
        eps = _float_or_none(fundamental.get("eps"))
        sps = _float_or_none(fundamental.get("sps"))
        bps = _float_or_none(fundamental.get("bps"))
        dividend_yield = _float_or_none(next_candidate.get("dividend_yield"))

        if price > 0 and eps is not None and eps > 0:
            next_candidate["per"] = round(price / eps, 2)
        if price > 0 and bps is not None and bps > 0:
            next_candidate["pbr"] = round(price / bps, 2)
        if price > 0 and sps is not None and sps > 0:
            next_candidate["psr"] = round(price / sps, 2)
            if eps is not None:
                next_candidate["net_margin"] = round(eps / sps * 100, 2)

        roe = _float_or_none(next_candidate.get("roe"))
        debt_ratio = _float_or_none(next_candidate.get("debt_ratio"))
        if roe is not None and debt_ratio is not None and debt_ratio > -100:
            next_candidate["roa"] = round(roe * 100 / (100 + max(debt_ratio, 0)), 2)

        per = _float_or_none(next_candidate.get("per"))
        if dividend_yield is not None and dividend_yield > 0 and per is not None and per > 0:
            next_candidate["payout_ratio"] = round(max(0, min(100, dividend_yield * per)), 2)
            next_candidate["dividend_stability_score"] = _derived_dividend_stability_score(next_candidate)

        rationale = [
            str(reason) for reason in next_candidate.get("rationale", []) if not str(reason).startswith("ROE ")
        ]
        revenue_growth = _float_or_none(next_candidate.get("revenue_growth"))
        roe = _float_or_none(next_candidate.get("roe"))
        if roe is not None and revenue_growth is not None:
            rationale.append(f"KIS 재무 ROE {roe:.1f}%, 매출성장률 {revenue_growth:.1f}%")
        rationale.append("KIS 재무비율로 성장성/수익성/밸류에이션을 보강")
        next_candidate["rationale"] = rationale

        risk_flags = [flag for flag in next_candidate.get("risk_flags", []) if flag != "재무지표 미연동"]
        debt_ratio = _float_or_none(next_candidate.get("debt_ratio"))
        if debt_ratio is not None and debt_ratio >= 200:
            risk_flags.append("부채비율 높음")
        if roe is not None and roe < 0:
            risk_flags.append("ROE 음수")
        next_candidate["risk_flags"] = risk_flags
        next_candidate["strategy_score"] = calculate_strategy_score(strategy_code, next_candidate)
        enriched.append(next_candidate)

    return sorted(enriched, key=lambda item: item["strategy_score"], reverse=True)


def _with_candidate_defaults(item: dict[str, Any]) -> dict[str, Any]:
    item.setdefault("psr", _derived_psr(item))
    item.setdefault("ev_ebitda", _derived_ev_ebitda(item))
    item.setdefault("fcf_yield", _derived_fcf_yield(item))
    item.setdefault("dividend_yield", _derived_dividend_yield(item))
    item.setdefault("payout_ratio", 25.0)
    item.setdefault("dividend_growth", _derived_dividend_growth(item))
    item.setdefault("dividend_streak_years", _derived_dividend_streak_years(item))
    item.setdefault("dividend_stability_score", _derived_dividend_stability_score(item))
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


def _with_quality_filter_flags(strategy_code: str, candidate: dict[str, Any]) -> dict[str, Any]:
    next_candidate = _with_candidate_defaults({**candidate})
    risk_flags = list(dict.fromkeys(str(flag) for flag in next_candidate.get("risk_flags", [])))

    if _fails_hard_exclusion(next_candidate):
        risk_flags.append("기본 제외 대상")
    if _fails_liquidity_filter(next_candidate):
        risk_flags.append("유동성 부족")
    if _fails_risk_exclusion_filter(next_candidate):
        risk_flags.append("리스크 제외 기준")
    if strategy_code in {"trend-breakout", "growth-breakout-leader"} and _numeric_value(
        next_candidate,
        "change_pct",
    ) >= 8:
        risk_flags.append("돌파 추격 위험")

    next_candidate["risk_flags"] = list(dict.fromkeys(risk_flags))
    return next_candidate


def _fails_hard_exclusion(candidate: dict[str, Any]) -> bool:
    name = str(candidate.get("name") or "")
    price = _numeric_value(candidate, "price")

    if price <= 0:
        return True
    if any(keyword in name.upper() for keyword in ("SPAC", "스팩", "ETN")):
        return True

    return False


def _fails_liquidity_filter(candidate: dict[str, Any]) -> bool:
    trading_value_100m = _numeric_value(candidate, "trading_value_krw_100m")
    avg_volume_10k = _numeric_value(candidate, "avg_volume_20d_10k")
    turnover_pct = _numeric_value(candidate, "turnover_pct")

    has_trading_value = trading_value_100m > 0
    has_avg_volume = avg_volume_10k > 0
    has_turnover = turnover_pct > 0

    if has_trading_value and trading_value_100m < 5:
        return True
    if has_avg_volume and avg_volume_10k < 1:
        return True
    if has_turnover and turnover_pct < 0.03:
        return True

    return False


def _fails_risk_exclusion_filter(candidate: dict[str, Any]) -> bool:
    short_sale_ratio = _numeric_value(candidate, "short_sale_ratio")
    margin_debt_change_5d = _numeric_value(candidate, "margin_debt_change_5d")
    volatility_20d = _numeric_value(candidate, "volatility_20d")
    drawdown_52w = _numeric_value(candidate, "drawdown_52w")
    debt_ratio = _numeric_value(candidate, "debt_ratio")
    roe = _numeric_value(candidate, "roe")

    if short_sale_ratio >= 15:
        return True
    if margin_debt_change_5d >= 40:
        return True
    if volatility_20d >= 90:
        return True
    if drawdown_52w <= -60:
        return True
    if debt_ratio >= 300:
        return True
    if roe <= -25:
        return True

    return False


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
        r"(?P<field>[\w가-힣_/%\s]+?)\s*(?P<operator>>=|<=|>|<|==)\s*"
        r"(?P<value>-?\d+(?:\.\d+)?)(?:\s*(?P<unit>억|조|만원|만주|주|%|점|년|배))?",
        condition,
    )
    if numeric_match:
        field = numeric_match.group("field")
        resolved_field = _resolve_numeric_formula_field(field)
        if resolved_field is None:
            return True, False
        value = _numeric_value(candidate, resolved_field)
        compare_value = _normalize_formula_compare_value(
            field=field,
            resolved_field=resolved_field,
            raw_value=float(numeric_match.group("value")),
            unit=numeric_match.group("unit") or "",
        )
        return _compare_numeric(value, numeric_match.group("operator"), compare_value), True

    return True, False


def _resolve_numeric_formula_field(field: str) -> str | None:
    stripped = field.strip()
    if stripped in NUMERIC_FORMULA_FIELD_ALIASES:
        return NUMERIC_FORMULA_FIELD_ALIASES[stripped]

    compact = re.sub(r"\s+", "", stripped).lower()
    if compact in NUMERIC_FORMULA_FIELD_ALIASES:
        return NUMERIC_FORMULA_FIELD_ALIASES[compact]

    return KOREAN_NUMERIC_FORMULA_FIELD_ALIASES.get(compact)


def _normalize_formula_compare_value(
    *,
    field: str,
    resolved_field: str,
    raw_value: float,
    unit: str,
) -> float:
    compact_field = re.sub(r"\s+", "", field).lower()
    if resolved_field == "market_cap" and unit == "억":
        return raw_value / 10_000
    if resolved_field == "trading_value_krw_100m" and unit == "조":
        return raw_value * 10_000
    if resolved_field == "avg_volume_20d_10k" and unit == "주":
        return raw_value / 10_000
    if compact_field == "현재가" and unit == "만원":
        return raw_value * 10_000
    return raw_value


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
        "dividend_growth": _metadata_float(metadata, "dividend_growth", _derived_dividend_growth(metadata)),
        "dividend_streak_years": round(
            _metadata_float(metadata, "dividend_streak_years", _derived_dividend_streak_years(metadata))
        ),
        "dividend_stability_score": clamp_score(
            _metadata_float(metadata, "dividend_stability_score", _derived_dividend_stability_score(metadata))
        ),
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


def _derived_dividend_growth(metadata: dict[str, Any]) -> float:
    dividend_yield = _float_or_none(metadata.get("dividend_yield"))
    if dividend_yield is None:
        dividend_yield = _derived_dividend_yield(metadata)
    if dividend_yield <= 0:
        return 0.0

    revenue_growth = _float_or_none(metadata.get("revenue_growth")) or 0
    eps_growth = _float_or_none(metadata.get("eps_growth")) or revenue_growth * 1.2
    roe = _float_or_none(metadata.get("roe")) or 0
    return round(max(-20.0, min(25.0, revenue_growth * 0.3 + eps_growth * 0.3 + roe * 0.08)), 2)


def _derived_dividend_streak_years(metadata: dict[str, Any]) -> int:
    dividend_yield = _float_or_none(metadata.get("dividend_yield"))
    if dividend_yield is None:
        dividend_yield = _derived_dividend_yield(metadata)
    if dividend_yield <= 0:
        return 0

    sector = str(metadata.get("sector") or "")
    payout_ratio = _float_or_none(metadata.get("payout_ratio")) or 25
    debt_ratio = _float_or_none(metadata.get("debt_ratio")) or 85
    base_years = 5
    if sector in {"금융", "산업재", "소비순환재"}:
        base_years += 3
    if payout_ratio <= 60:
        base_years += 2
    if debt_ratio <= 120:
        base_years += 1
    return max(0, min(15, base_years))


def _derived_dividend_stability_score(metadata: dict[str, Any]) -> int:
    dividend_yield = _float_or_none(metadata.get("dividend_yield"))
    if dividend_yield is None:
        dividend_yield = _derived_dividend_yield(metadata)
    if dividend_yield <= 0:
        return 0

    payout_ratio = _float_or_none(metadata.get("payout_ratio")) or 25
    debt_ratio = _float_or_none(metadata.get("debt_ratio")) or 85
    fcf_yield = _float_or_none(metadata.get("fcf_yield"))
    if fcf_yield is None:
        fcf_yield = _derived_fcf_yield(metadata)
    dividend_growth = _float_or_none(metadata.get("dividend_growth"))
    if dividend_growth is None:
        dividend_growth = _derived_dividend_growth(metadata)

    score = (
        50
        + min(dividend_yield, 6) * 4
        + max(min(dividend_growth, 12), 0) * 1.2
        + max(min(fcf_yield, 8), -4) * 2
        - max(payout_ratio - 65, 0) * 0.7
        - max(debt_ratio - 150, 0) * 0.12
    )
    return clamp_score(score)


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
