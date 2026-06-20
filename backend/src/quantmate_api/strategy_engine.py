from __future__ import annotations

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


def build_strategy_candidates(strategy_code: str, limit: int = 12) -> list[dict[str, Any]]:
    rows = [
        {
            **item,
            "strategy_score": calculate_strategy_score(strategy_code, item),
            "rationale": build_rationale(strategy_code, item),
            "risk_flags": build_risk_flags(item),
        }
        for item in CANDIDATE_UNIVERSE
    ]

    return sorted(rows, key=lambda item: item["strategy_score"], reverse=True)[:limit]


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


def format_signed_percent(value: float) -> str:
    return f"{value:+.1f}%"


def format_signed_amount(value: float) -> str:
    return f"{value:+,.0f}억"
