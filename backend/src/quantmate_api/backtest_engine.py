from __future__ import annotations

import math
from datetime import UTC, datetime
from statistics import fmean, pstdev
from typing import Any

from quantmate_api.strategy_engine import build_strategy_candidates


BASE_ANNUAL_RETURNS = {
    2018: -9.8,
    2019: 10.7,
    2020: 7.4,
    2021: 11.8,
    2022: -8.6,
    2023: 18.4,
    2024: 13.2,
    2025: 9.6,
    2026: 4.2,
}

STRATEGY_PROFILES = {
    "relative-momentum-swing": {
        "return_bias": 2.1,
        "volatility_bias": 1.1,
        "yield_pct": 1.4,
        "monthly_turnover_pct": 18.0,
    },
    "value-quality-factor": {
        "return_bias": 0.8,
        "volatility_bias": 0.75,
        "yield_pct": 2.6,
        "monthly_turnover_pct": 8.0,
    },
    "growth-breakout-leader": {
        "return_bias": 2.8,
        "volatility_bias": 1.35,
        "yield_pct": 0.7,
        "monthly_turnover_pct": 22.0,
    },
    "trend-breakout": {
        "return_bias": 1.7,
        "volatility_bias": 1.45,
        "yield_pct": 0.9,
        "monthly_turnover_pct": 28.0,
    },
    "supply-demand-accumulation": {
        "return_bias": 1.5,
        "volatility_bias": 1.2,
        "yield_pct": 1.1,
        "monthly_turnover_pct": 20.0,
    },
    "low-volatility-defensive": {
        "return_bias": -0.2,
        "volatility_bias": 0.55,
        "yield_pct": 2.1,
        "monthly_turnover_pct": 6.0,
    },
}


def build_sample_backtest(
    *,
    strategy_code: str,
    strategy_name: str,
    start_year: int,
    end_year: int,
    initial_amount: int,
) -> dict[str, Any]:
    """Build a deterministic sample result behind the same contract as the real engine.

    KRX 일봉 적재 전까지는 화면과 API 계약 검증이 목적이다. 실제 엔진이 붙으면 이 함수의
    내부 계산만 교체하고 응답 형태는 유지한다.
    """

    first_year = min(start_year, end_year)
    last_year = max(start_year, end_year)
    years = list(range(first_year, last_year + 1))
    profile = STRATEGY_PROFILES.get(strategy_code, STRATEGY_PROFILES["relative-momentum-swing"])

    annual_returns = [
        _strategy_return_for_year(strategy_code=strategy_code, year=year, profile=profile)
        for year in years
    ]
    equity_curve, annual_rows = _build_equity_curve(
        years=years,
        annual_returns=annual_returns,
        initial_amount=initial_amount,
        yield_pct=float(profile["yield_pct"]),
    )
    final_amount = annual_rows[-1]["balance"] if annual_rows else initial_amount
    metrics = _build_metrics(
        initial_amount=initial_amount,
        final_amount=final_amount,
        years=years,
        annual_returns=annual_returns,
        equity_curve=equity_curve,
        monthly_turnover_pct=float(profile["monthly_turnover_pct"]),
    )

    return {
        "strategy_code": strategy_code,
        "strategy_name": strategy_name,
        "source": "sample-backtest-engine",
        "period": f"{first_year} ~ {last_year}",
        "initial_amount": initial_amount,
        "final_amount": final_amount,
        "run_at": datetime.now(UTC).isoformat(),
        "notice": (
            "현재 결과는 서버 샘플 백테스트 엔진으로 계산했습니다. "
            "KRX 일봉 데이터 적재 후 같은 API를 실제 리밸런싱 계산으로 교체합니다."
        ),
        "metrics": metrics,
        "annual_returns": annual_rows,
        "equity_curve": equity_curve,
        "rebalance_history": _build_rebalance_history(strategy_code),
    }


def _strategy_return_for_year(
    *,
    strategy_code: str,
    year: int,
    profile: dict[str, float],
) -> float:
    base = BASE_ANNUAL_RETURNS.get(year, _fallback_market_return(year))
    cycle_adjustment = ((year + len(strategy_code)) % 5 - 2) * 0.7
    volatility_bias = float(profile["volatility_bias"])
    return round((base + float(profile["return_bias"]) + cycle_adjustment) * volatility_bias, 1)


def _fallback_market_return(year: int) -> float:
    values = list(BASE_ANNUAL_RETURNS.values())
    return values[abs(year) % len(values)]


def _build_equity_curve(
    *,
    years: list[int],
    annual_returns: list[float],
    initial_amount: int,
    yield_pct: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    balance = float(initial_amount)
    curve: list[dict[str, Any]] = []
    annual_rows: list[dict[str, Any]] = []

    for year, annual_return in zip(years, annual_returns, strict=True):
        monthly_return = math.pow(1 + annual_return / 100, 1 / 12) - 1

        for month in range(1, 13):
            balance *= 1 + monthly_return
            curve.append(
                {
                    "label": f"{year}.{month:02d}",
                    "portfolio": round(balance),
                }
            )

        annual_balance = round(balance)
        annual_rows.append(
            {
                "year": str(year),
                "portfolio_return": annual_return,
                "yield_pct": round(yield_pct, 1),
                "balance": annual_balance,
                "income": round(annual_balance * (yield_pct / 100)),
            }
        )

    return curve, annual_rows


def _build_metrics(
    *,
    initial_amount: int,
    final_amount: int,
    years: list[int],
    annual_returns: list[float],
    equity_curve: list[dict[str, Any]],
    monthly_turnover_pct: float,
) -> list[dict[str, str]]:
    year_count = max(len(years), 1)
    annual_return_decimals = [value / 100 for value in annual_returns]
    cagr = math.pow(final_amount / initial_amount, 1 / year_count) - 1
    volatility = pstdev(annual_return_decimals) if len(annual_return_decimals) > 1 else 0
    downside_returns = [value for value in annual_return_decimals if value < 0]
    downside_deviation = (
        math.sqrt(fmean([value * value for value in downside_returns]))
        if downside_returns
        else volatility
    )
    sharpe = cagr / volatility if volatility else 0
    sortino = cagr / downside_deviation if downside_deviation else 0
    best_index = max(range(len(annual_returns)), key=annual_returns.__getitem__)
    worst_index = min(range(len(annual_returns)), key=annual_returns.__getitem__)

    return [
        {"metric": "시작금액", "value": _format_krw(initial_amount)},
        {"metric": "종료금액", "value": _format_krw(final_amount)},
        {"metric": "연평균 수익률(CAGR)", "value": _format_percent(cagr * 100)},
        {"metric": "변동성", "value": _format_percent(volatility * 100)},
        {
            "metric": "최고 연도",
            "value": f"{years[best_index]} · {_format_percent(annual_returns[best_index])}",
        },
        {
            "metric": "최저 연도",
            "value": f"{years[worst_index]} · {_format_percent(annual_returns[worst_index])}",
        },
        {"metric": "최대 낙폭(MDD)", "value": _format_percent(_calculate_mdd(equity_curve))},
        {"metric": "샤프 비율", "value": f"{sharpe:.2f}"},
        {"metric": "소르티노 비율", "value": f"{sortino:.2f}"},
        {"metric": "월평균 회전율", "value": _format_percent(monthly_turnover_pct)},
    ]


def _calculate_mdd(equity_curve: list[dict[str, Any]]) -> float:
    peak = 0
    max_drawdown = 0.0

    for point in equity_curve:
        value = int(point["portfolio"])
        peak = max(peak, value)
        if peak > 0:
            drawdown = (value / peak - 1) * 100
            max_drawdown = min(max_drawdown, drawdown)

    return max_drawdown


def _build_rebalance_history(strategy_code: str) -> list[dict[str, str]]:
    candidates = build_strategy_candidates(strategy_code=strategy_code, limit=12)
    months = ["2025-01", "2025-02", "2025-03", "2025-04"]
    turnovers = ["18.0%", "24.0%", "16.0%", "12.0%"]
    rows: list[dict[str, str]] = []

    for index, month in enumerate(months):
        start = index * 2
        entries = [item["name"] for item in candidates[start : start + 3]]
        exits = [item["name"] for item in candidates[start + 6 : start + 8]]
        rows.append(
            {
                "date": month,
                "holdings": "10종목",
                "entries": ", ".join(entries) if entries else "없음",
                "exits": ", ".join(exits) if exits else "없음",
                "turnover": turnovers[index],
            }
        )

    return rows


def _format_krw(value: int) -> str:
    return f"{value:,.0f}원"


def _format_percent(value: float) -> str:
    return f"{value:.1f}%"
