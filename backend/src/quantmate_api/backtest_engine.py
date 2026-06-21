from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from statistics import fmean, pstdev
from typing import Any

from quantmate_api.strategy_engine import (
    apply_user_strategy_formula,
    build_strategy_candidates,
    build_strategy_candidates_from_daily_prices,
)
from quantmate_api.time_utils import now_kst


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


def build_daily_price_backtest(
    *,
    strategy_code: str,
    strategy_name: str,
    start_year: int,
    end_year: int,
    initial_amount: int,
    price_rows: list[dict[str, Any]],
    provider: str,
    candidate_formula: str | None = None,
) -> dict[str, Any] | None:
    first_year = min(start_year, end_year)
    last_year = max(start_year, end_year)

    symbol_rows = _group_price_rows_by_symbol(price_rows)
    month_keys = _month_keys_for_period(price_rows, first_year=first_year, last_year=last_year)

    if len(month_keys) < 2:
        return None

    balance = float(initial_amount)
    equity_curve: list[dict[str, Any]] = []
    annual_start_balance: dict[int, float] = {}
    annual_end_balance: dict[int, float] = {}
    previous_holdings: list[str] = []
    rebalance_history: list[dict[str, str]] = []
    turnover_values: list[float] = []
    trade_returns: list[float] = []
    symbol_names = _symbol_names_from_price_rows(price_rows)

    for month_key in month_keys:
        month_start = _month_start_date(month_key)
        ranking_rows = [
            row
            for rows in symbol_rows.values()
            for row in rows
            if _coerce_date(row["trade_date"]) < month_start
        ]
        ranked_candidates = build_strategy_candidates_from_daily_prices(
            strategy_code=strategy_code,
            price_rows=ranking_rows,
            limit=10,
        )
        if candidate_formula:
            ranked_candidates, _unsupported_conditions = apply_user_strategy_formula(
                candidates=ranked_candidates,
                formula=candidate_formula,
            )
            ranked_candidates = ranked_candidates[:10]
        holdings = [str(candidate["symbol"]) for candidate in ranked_candidates]

        if not holdings:
            continue

        monthly_symbol_returns = [
            month_return
            for symbol in holdings
            if (month_return := _symbol_month_return(symbol_rows.get(symbol, []), month_key)) is not None
        ]

        if not monthly_symbol_returns:
            continue

        trade_returns.extend(monthly_symbol_returns)
        monthly_return = fmean(monthly_symbol_returns)
        year = int(month_key[:4])
        annual_start_balance.setdefault(year, balance)
        balance *= 1 + monthly_return
        annual_end_balance[year] = balance
        equity_curve.append({"label": month_key.replace("-", "."), "portfolio": round(balance)})
        turnover = _calculate_turnover(previous_holdings=previous_holdings, holdings=holdings)
        turnover_values.append(turnover)
        rebalance_history.append(
            _build_dynamic_rebalance_row(
                month_key=month_key,
                previous_holdings=previous_holdings,
                holdings=holdings,
                symbol_names=symbol_names,
                turnover=turnover,
            )
        )
        previous_holdings = holdings

    annual_rows: list[dict[str, Any]] = []
    annual_returns: list[float] = []
    for year in range(first_year, last_year + 1):
        if year not in annual_start_balance or year not in annual_end_balance:
            continue

        start_balance = annual_start_balance[year]
        end_balance = annual_end_balance[year]
        annual_return = (end_balance / start_balance - 1) * 100 if start_balance else 0
        annual_returns.append(round(annual_return, 1))
        annual_rows.append(
            {
                "year": str(year),
                "portfolio_return": round(annual_return, 1),
                "yield_pct": 0.0,
                "balance": round(end_balance),
                "income": 0,
            }
        )

    if not annual_rows:
        return None

    final_amount = int(equity_curve[-1]["portfolio"])
    years = [int(row["year"]) for row in annual_rows]
    metrics = _build_metrics(
        initial_amount=initial_amount,
        final_amount=final_amount,
        years=years,
        annual_returns=annual_returns,
        equity_curve=equity_curve,
        monthly_turnover_pct=fmean(turnover_values) if turnover_values else 0.0,
        trade_returns=trade_returns,
    )

    return {
        "strategy_code": strategy_code,
        "strategy_name": strategy_name,
        "source": f"daily-price-backtest:{provider}",
        "period": f"{first_year} ~ {last_year}",
        "initial_amount": initial_amount,
        "final_amount": final_amount,
        "run_at": now_kst().isoformat(),
        "notice": (
            f"{provider} 일봉 데이터로 계산했습니다. "
            "매월 직전까지의 가격 데이터로 후보를 다시 선정하고, "
            "상위 후보 동일비중 월별 리밸런싱으로 계산합니다."
        ),
        "metrics": metrics,
        "annual_returns": annual_rows,
        "equity_curve": equity_curve,
        "rebalance_history": rebalance_history,
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
        trade_returns=[value / 100 for value in annual_returns],
    )

    return {
        "strategy_code": strategy_code,
        "strategy_name": strategy_name,
        "source": "sample-backtest-engine",
        "period": f"{first_year} ~ {last_year}",
        "initial_amount": initial_amount,
        "final_amount": final_amount,
        "run_at": now_kst().isoformat(),
        "notice": (
            "현재 결과는 서버 샘플 백테스트 엔진으로 계산했습니다. "
            "KRX 일봉 데이터 적재 후 같은 API를 실제 리밸런싱 계산으로 교체합니다."
        ),
        "metrics": metrics,
        "annual_returns": annual_rows,
        "equity_curve": equity_curve,
        "rebalance_history": _build_rebalance_history(strategy_code),
    }


def _build_monthly_returns(price_rows: list[dict[str, Any]]) -> list[tuple[str, float]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in price_rows:
        trade_date = _coerce_date(row["trade_date"])
        month_key = f"{trade_date.year}-{trade_date.month:02d}"
        grouped[(str(row["symbol"]), month_key)].append(row)

    symbol_month_returns: dict[str, list[float]] = defaultdict(list)
    for (_symbol, month_key), rows in grouped.items():
        ordered = sorted(rows, key=lambda item: _coerce_date(item["trade_date"]))
        if len(ordered) < 2:
            continue

        start_price = float(ordered[0]["close_price"])
        end_price = float(ordered[-1]["close_price"])
        if start_price <= 0:
            continue

        symbol_month_returns[month_key].append(end_price / start_price - 1)

    monthly_returns = [
        (month_key, fmean(returns))
        for month_key, returns in sorted(symbol_month_returns.items())
        if returns
    ]
    return monthly_returns


def _group_price_rows_by_symbol(price_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in price_rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol:
            grouped[symbol].append(row)

    return {
        symbol: sorted(rows, key=lambda item: _coerce_date(item["trade_date"]))
        for symbol, rows in grouped.items()
    }


def _month_keys_for_period(
    price_rows: list[dict[str, Any]],
    *,
    first_year: int,
    last_year: int,
) -> list[str]:
    month_keys = {
        f"{trade_date.year}-{trade_date.month:02d}"
        for row in price_rows
        if first_year <= (trade_date := _coerce_date(row["trade_date"])).year <= last_year
    }
    return sorted(month_keys)


def _month_start_date(month_key: str) -> date:
    year, month = month_key.split("-")
    return date(int(year), int(month), 1)


def _symbol_month_return(rows: list[dict[str, Any]], month_key: str) -> float | None:
    month_rows = [
        row
        for row in rows
        if f"{_coerce_date(row['trade_date']).year}-{_coerce_date(row['trade_date']).month:02d}" == month_key
    ]

    if len(month_rows) < 2:
        return None

    start_price = float(month_rows[0]["close_price"])
    end_price = float(month_rows[-1]["close_price"])
    if start_price <= 0:
        return None

    return end_price / start_price - 1


def _symbol_names_from_price_rows(price_rows: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(row["symbol"]): str(row.get("name") or row["symbol"])
        for row in price_rows
    }


def _calculate_turnover(*, previous_holdings: list[str], holdings: list[str]) -> float:
    if not holdings:
        return 0.0
    if not previous_holdings:
        return 100.0

    previous = set(previous_holdings)
    current = set(holdings)
    changed = len(current - previous) + len(previous - current)
    base = max(len(previous) + len(current), 1)
    return changed / base * 100


def _build_dynamic_rebalance_row(
    *,
    month_key: str,
    previous_holdings: list[str],
    holdings: list[str],
    symbol_names: dict[str, str],
    turnover: float,
) -> dict[str, str]:
    previous = set(previous_holdings)
    current = set(holdings)
    entries = [symbol_names.get(symbol, symbol) for symbol in holdings if symbol not in previous]
    exits = [symbol_names.get(symbol, symbol) for symbol in previous_holdings if symbol not in current]

    if not entries and holdings:
        entries = [symbol_names.get(symbol, symbol) for symbol in holdings]

    return {
        "date": month_key,
        "holdings": f"{len(holdings)}종목",
        "entries": ", ".join(entries) if entries else "없음",
        "exits": ", ".join(exits) if exits else "없음",
        "turnover": _format_percent(turnover),
    }


def _coerce_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("거래일 형식이 올바르지 않습니다.")


def _build_daily_price_rebalance_history(
    holdings: list[str],
    monthly_returns: list[tuple[str, float]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    displayed_holdings = ", ".join(holdings)

    for month_key, monthly_return in monthly_returns[-6:]:
        rows.append(
            {
                "date": month_key,
                "holdings": f"{len(holdings)}종목",
                "entries": displayed_holdings or "없음",
                "exits": "월말 동일비중 재조정",
                "turnover": _format_percent(abs(monthly_return) * 100),
            }
        )

    return rows


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
    trade_returns: list[float] | None = None,
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
    effective_trade_returns = trade_returns or annual_return_decimals
    trade_count = len(effective_trade_returns)
    win_rate = (
        sum(1 for value in effective_trade_returns if value > 0) / trade_count * 100
        if trade_count
        else 0.0
    )

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
        {"metric": "거래 승률", "value": _format_percent(win_rate)},
        {"metric": "거래 수", "value": f"{trade_count}건"},
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
