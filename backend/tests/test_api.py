import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import quantmate_api.main as main_module
import quantmate_api.market_data as market_data_module

from quantmate_api.main import app
from quantmate_api.models import (
    BacktestRun,
    Base,
    DailyPrice,
    FundamentalRatio,
    Instrument,
    Market,
    QuoteSnapshot,
    RiskIndicatorDaily,
    SupplyFlowDaily,
)
from quantmate_api.strategy_engine import CANDIDATE_UNIVERSE


client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_kis_auto_import_by_default(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: False)

    def unavailable_kis_current_price(symbol: str) -> dict[str, object]:
        raise main_module.MarketDataProviderUnavailable(f"KIS 현재가 테스트 차단: {symbol}")

    def unavailable_kis_market_cap_ranking(limit: int = 50, market: str = "ALL") -> list[dict[str, object]]:
        raise main_module.MarketDataProviderUnavailable(f"KIS 시가총액 랭킹 테스트 차단: {market} {limit}")

    def unavailable_kis_investor_trade_daily(
        symbol: str,
        base_date: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, object]]:
        raise main_module.MarketDataProviderUnavailable(f"KIS 수급 테스트 차단: {symbol}")

    def unavailable_kis_daily_short_sale(
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, object]]:
        raise main_module.MarketDataProviderUnavailable(f"KIS 공매도 테스트 차단: {symbol}")

    def unavailable_kis_daily_credit_balance(
        symbol: str,
        base_date: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, object]]:
        raise main_module.MarketDataProviderUnavailable(f"KIS 신용잔고 테스트 차단: {symbol}")

    def unavailable_kis_financial_ratios(
        symbol: str,
        period_type: str = "annual",
        limit: int = 8,
    ) -> list[dict[str, object]]:
        raise main_module.MarketDataProviderUnavailable(f"KIS 재무비율 테스트 차단: {symbol}")

    monkeypatch.setattr(main_module, "fetch_kis_current_price", unavailable_kis_current_price)
    monkeypatch.setattr(main_module, "fetch_kis_market_cap_ranking", unavailable_kis_market_cap_ranking)
    monkeypatch.setattr(main_module, "fetch_kis_investor_trade_daily", unavailable_kis_investor_trade_daily)
    monkeypatch.setattr(main_module, "fetch_kis_daily_short_sale", unavailable_kis_daily_short_sale)
    monkeypatch.setattr(main_module, "fetch_kis_daily_credit_balance", unavailable_kis_daily_credit_balance)
    monkeypatch.setattr(main_module, "fetch_kis_financial_ratios", unavailable_kis_financial_ratios)


def disable_kis_auto_import(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: False)


def stub_empty_yahoo_prices(monkeypatch) -> None:
    disable_kis_auto_import(monkeypatch)

    def fake_fetch_yahoo_daily_prices(
        symbol: str,
        exchange: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(main_module, "fetch_yahoo_daily_prices", fake_fetch_yahoo_daily_prices)
    monkeypatch.setattr(main_module, "fetch_yfinance_symbol_daily_prices", lambda **_kwargs: [])


def use_sqlite_session(monkeypatch) -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(main_module, "SessionLocal", session_factory)
    return session_factory


def seed_daily_prices(
    session_factory: sessionmaker,
    *,
    symbols: list[dict[str, object]],
    provider: str = "Yahoo Finance",
    start: date = date(2025, 1, 1),
    days: int = 80,
) -> None:
    with session_factory() as session:
        market = Market(
            code="KR",
            name="한국 주식",
            country="KR",
            currency="KRW",
            timezone="Asia/Seoul",
        )
        session.add(market)
        session.flush()

        for symbol_index, item in enumerate(symbols):
            instrument = Instrument(
                market_id=market.id,
                symbol=str(item["symbol"]),
                name=str(item["name"]),
                exchange=str(item["exchange"]),
                asset_type="stock",
            )
            session.add(instrument)
            session.flush()

            base_price = 10000 + symbol_index * 1000
            drift = 1 + symbol_index * 0.15
            for day_index in range(days):
                trade_date = start + timedelta(days=day_index)
                close_price = base_price + day_index * drift * 10
                session.add(
                    DailyPrice(
                        instrument_id=instrument.id,
                        trade_date=trade_date,
                        open_price=close_price - 30,
                        high_price=close_price + 50,
                        low_price=close_price - 60,
                        close_price=close_price,
                        volume=100000 + symbol_index * 10000 + day_index * 100,
                        trading_value=close_price * (100000 + symbol_index * 10000 + day_index * 100),
                        provider=provider,
                        is_adjusted=False,
                    )
                )

        session.commit()


def test_health_endpoint() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["live_trading_enabled"] is False


def test_dashboard_contains_initial_mvp_data() -> None:
    response = client.get("/api/dashboard")
    data = response.json()

    assert response.status_code == 200
    assert len(data["strategies"]) >= 6
    assert len(data["recommendations"]) >= 3
    assert data["backtest"]["metrics"]
    assert data["modes"][0]["code"] == "research"
    assert all(mode["code"] != "paper" for mode in data["modes"])


def test_strategy_candidates_returns_ranked_rows() -> None:
    response = client.get("/api/strategies/relative-momentum-swing/candidates")
    data = response.json()

    assert response.status_code == 200
    assert data["strategy_code"] == "relative-momentum-swing"
    assert len(data["candidates"]) >= 10
    scores = [item["strategy_score"] for item in data["candidates"]]
    assert scores == sorted(scores, reverse=True)
    assert data["candidates"][0]["rationale"]


def test_strategy_candidates_use_daily_prices_when_available(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:10],
        start=date(2026, 1, 1),
        days=40,
    )

    response = client.get("/api/strategies/relative-momentum-swing/candidates")
    data = response.json()

    assert response.status_code == 200
    assert data["source"] == "daily-price-candidates:Yahoo Finance"
    assert len(data["candidates"]) == 10
    assert "수익률" in data["candidates"][0]["rationale"][0]
    assert [item["strategy_score"] for item in data["candidates"]] == sorted(
        [item["strategy_score"] for item in data["candidates"]],
        reverse=True,
    )


def test_strategy_candidates_enrich_with_kis_quote_snapshot(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:10],
        start=date(2026, 1, 1),
        days=40,
    )

    with session_factory() as session:
        instrument = session.scalar(select(Instrument).where(Instrument.symbol == "005930"))
        session.add(
            QuoteSnapshot(
                instrument_id=instrument.id,
                snapshot_date=date.today(),
                provider=main_module.KIS_QUOTE_SNAPSHOT_PROVIDER,
                price=78000,
                change_pct=1.2,
                volume=1000000,
                trading_value=78000000000,
                market_cap=4650000,
                per=12.5,
                pbr=1.1,
                eps=6200,
                bps=70000,
                turnover_pct=0.4,
                foreign_holding_rate=52.3,
                foreign_net_buy_qty=100000,
                program_net_buy_qty=50000,
                high_52w=90000,
                low_52w=62000,
            )
        )
        session.commit()

    response = client.get("/api/strategies/relative-momentum-swing/candidates")
    data = response.json()
    samsung = next(item for item in data["candidates"] if item["symbol"] == "005930")

    assert response.status_code == 200
    assert "KIS 현재가" in data["source"]
    assert samsung["price"] != 78000
    assert samsung["per"] == 12.5
    assert samsung["pbr"] == 1.1
    assert samsung["market_cap"] == 465


def test_strategy_candidates_enrich_with_kis_supply_flow(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:10],
        start=date(2026, 1, 1),
        days=40,
    )

    with session_factory() as session:
        instrument = session.scalar(select(Instrument).where(Instrument.symbol == "005930"))
        for index in range(5):
            session.add(
                SupplyFlowDaily(
                    instrument_id=instrument.id,
                    trade_date=main_module.today_kst() - timedelta(days=4 - index),
                    provider=main_module.KIS_SUPPLY_FLOW_PROVIDER,
                    foreign_net_buy_qty=1000,
                    institution_net_buy_qty=500,
                    pension_net_buy_qty=100,
                    foreign_net_buy_value=100_000_000_000,
                    institution_net_buy_value=50_000_000_000,
                    pension_net_buy_value=10_000_000_000,
                    individual_net_buy_value=-160_000_000_000,
                )
            )
        session.commit()

    response = client.get("/api/strategies/relative-momentum-swing/candidates")
    data = response.json()
    samsung = next(item for item in data["candidates"] if item["symbol"] == "005930")

    assert response.status_code == 200
    assert "KIS 수급" in data["source"]
    assert samsung["foreign_net_buy_5d"] == 5000
    assert samsung["institution_net_buy_5d"] == 2500
    assert samsung["pension_net_buy_20d"] == 500
    assert samsung["consecutive_foreign_buy_days"] == 5
    assert "KIS 투자자별 매매동향으로 수급 보강" in samsung["rationale"]


def test_strategy_candidates_enrich_with_kis_fundamentals(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:10],
        start=date(2026, 1, 1),
        days=40,
    )

    with session_factory() as session:
        instrument = session.scalar(select(Instrument).where(Instrument.symbol == "005930"))
        session.add(
            FundamentalRatio(
                instrument_id=instrument.id,
                fiscal_period="202603",
                period_type="annual",
                provider=main_module.KIS_FUNDAMENTAL_PROVIDER,
                revenue_growth=99.9,
                operating_income_growth=88.8,
                net_income_growth=77.7,
                roe=0,
                eps=4300,
                sps=130000,
                bps=90000,
                reserve_ratio=1300,
                debt_ratio=55.5,
            )
        )
        session.add(
            FundamentalRatio(
                instrument_id=instrument.id,
                fiscal_period="202512",
                period_type="annual",
                provider=main_module.KIS_FUNDAMENTAL_PROVIDER,
                revenue_growth=12.4,
                operating_income_growth=23.5,
                net_income_growth=34.6,
                roe=15.7,
                eps=4200,
                sps=120000,
                bps=80000,
                reserve_ratio=1200,
                debt_ratio=42.1,
            )
        )
        session.commit()

    response = client.get("/api/strategies/relative-momentum-swing/candidates")
    data = response.json()
    samsung = next(item for item in data["candidates"] if item["symbol"] == "005930")

    assert response.status_code == 200
    assert "KIS 재무" in data["source"]
    assert samsung["revenue_growth"] == 12.4
    assert samsung["operating_income_growth"] == 23.5
    assert samsung["eps_growth"] == 34.6
    assert samsung["roe"] == 15.7
    assert samsung["debt_ratio"] == 42.1
    assert "KIS 재무비율로 성장성/수익성/부채비율 보강" in samsung["rationale"]


def test_strategy_candidates_enrich_with_kis_risk_indicators(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:10],
        start=date(2026, 1, 1),
        days=40,
    )

    with session_factory() as session:
        instrument = session.scalar(select(Instrument).where(Instrument.symbol == "005930"))
        for index in range(6):
            session.add(
                RiskIndicatorDaily(
                    instrument_id=instrument.id,
                    trade_date=main_module.today_kst() - timedelta(days=5 - index),
                    provider=main_module.KIS_RISK_INDICATOR_PROVIDER,
                    short_sale_volume=1000 + index,
                    short_sale_volume_ratio=3.5 + index,
                    short_sale_value=100_000_000,
                    short_sale_value_ratio=4.0 + index,
                    margin_loan_balance=100_000_000_000 + index * 10_000_000_000,
                    margin_loan_balance_rate=1.2,
                    margin_loan_new_amount=12_000_000_000,
                    margin_loan_redeem_amount=8_000_000_000,
                    stock_loan_balance=1_000_000_000,
                    stock_loan_balance_rate=0.1,
                )
            )
        session.commit()

    response = client.get("/api/strategies/relative-momentum-swing/candidates")
    data = response.json()
    samsung = next(item for item in data["candidates"] if item["symbol"] == "005930")

    assert response.status_code == 200
    assert "KIS 리스크" in data["source"]
    assert samsung["short_sale_ratio"] == 8.5
    assert samsung["margin_debt_change_5d"] == 50.0
    assert "KIS 공매도/신용잔고 지표로 리스크 보강" in samsung["rationale"]
    assert "공매도 비중 높음" in samsung["risk_flags"]
    assert "신용잔고 단기 증가" in samsung["risk_flags"]


def test_strategy_candidates_auto_import_partial_kis_risk_indicators(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:10],
        start=date(2026, 1, 1),
        days=40,
    )
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: True)

    def fake_fetch_kis_daily_short_sale(
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, object]]:
        return [
            {
                "provider": "KIS Open API",
                "symbol": symbol,
                "trade_date": main_module.today_kst().isoformat(),
                "short_sale_volume": 1000,
                "short_sale_volume_ratio": 9.2,
                "short_sale_value": 300_000_000,
                "short_sale_value_ratio": 9.1,
            }
        ]

    def rate_limited_kis_daily_credit_balance(
        symbol: str,
        base_date: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, object]]:
        raise main_module.MarketDataProviderUnavailable("KIS Open API 호출 실패: HTTP 500 초당 거래건수를 초과하였습니다.")

    monkeypatch.setattr(main_module, "fetch_kis_daily_short_sale", fake_fetch_kis_daily_short_sale)
    monkeypatch.setattr(main_module, "fetch_kis_daily_credit_balance", rate_limited_kis_daily_credit_balance)

    response = client.get("/api/strategies/relative-momentum-swing/candidates")
    data = response.json()
    risk_enriched = next(item for item in data["candidates"] if item["short_sale_ratio"] == 9.2)

    assert response.status_code == 200
    assert "KIS 리스크" in data["source"]
    assert "공매도 비중 높음" in risk_enriched["risk_flags"]

    with session_factory() as session:
        saved_count = session.scalar(select(func.count()).select_from(RiskIndicatorDaily))

    assert saved_count == 1


def test_strategy_candidates_auto_import_kis_before_yahoo(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: True)

    yahoo_called = False

    def fake_fetch_kis_daily_prices(
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        is_adjusted: bool = False,
    ) -> list[dict[str, object]]:
        base_price = 10000 + int(symbol[-2:]) * 10
        return [
            {
                "symbol": symbol,
                "trade_date": (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
                "open": base_price + index,
                "high": base_price + index + 10,
                "low": base_price + index - 10,
                "close": base_price + index * 2,
                "adjusted_close": None,
                "volume": 100000 + index,
                "trading_value": (base_price + index * 2) * (100000 + index),
                "provider": "KIS Open API",
            }
            for index in range(40)
        ]

    def fake_fetch_yahoo_daily_prices(
        symbol: str,
        exchange: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        nonlocal yahoo_called
        yahoo_called = True
        return []

    monkeypatch.setattr(main_module, "fetch_kis_daily_prices", fake_fetch_kis_daily_prices)
    monkeypatch.setattr(main_module, "fetch_yahoo_daily_prices", fake_fetch_yahoo_daily_prices)

    response = client.get("/api/strategies/relative-momentum-swing/candidates")
    data = response.json()

    assert response.status_code == 200
    assert data["source"] == "daily-price-candidates:KIS Open API"
    assert len(data["candidates"]) >= 10
    assert yahoo_called is False


def test_screener_search_applies_formula_on_server(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:10],
        start=date(2026, 1, 1),
        days=40,
    )

    response = client.post(
        "/api/screener/search",
        json={
            "strategy_code": "relative-momentum-swing",
            "formula": 'keyword contains "삼성" AND close > ma20',
            "limit": 20,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["source"].endswith(":screener-filtered")
    assert data["unsupported_conditions"] == []
    assert [item["symbol"] for item in data["candidates"]] == ["005930"]


def test_strategy_candidates_unknown_strategy_returns_404() -> None:
    response = client.get("/api/strategies/unknown/candidates")

    assert response.status_code == 404


def test_backtest_run_returns_monthly_equity_curve(monkeypatch) -> None:
    stub_empty_yahoo_prices(monkeypatch)

    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": "relative-momentum-swing",
            "start_year": 2024,
            "end_year": 2025,
            "initial_amount": 10000000,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["strategy_code"] == "relative-momentum-swing"
    assert data["period"] == "2024 ~ 2025"
    assert data["initial_amount"] == 10000000
    assert data["final_amount"] != data["initial_amount"]
    assert len(data["annual_returns"]) == 2
    assert len(data["equity_curve"]) == 24
    assert data["equity_curve"][0]["label"] == "2024.01"
    assert data["rebalance_history"]
    assert "연평균 수익률(CAGR)" in {item["metric"] for item in data["metrics"]}


def test_backtest_run_uses_daily_price_dynamic_rebalance(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:8],
        start=date(2025, 1, 1),
        days=470,
    )
    stub_empty_yahoo_prices(monkeypatch)

    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": "trend-breakout",
            "start_year": 2026,
            "end_year": 2026,
            "initial_amount": 10000000,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["source"] == "daily-price-backtest:Yahoo Finance"
    assert "매월 직전까지의 가격 데이터" in data["notice"]
    assert data["final_amount"] != data["initial_amount"]
    assert len(data["rebalance_history"]) >= 2
    assert all("월말 동일비중" not in row["exits"] for row in data["rebalance_history"])
    metrics = {item["metric"]: item["value"] for item in data["metrics"]}
    assert "거래 승률" in metrics
    assert metrics["거래 수"].endswith("건")


def test_backtest_run_auto_imports_kis_before_yahoo(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: True)
    monkeypatch.setattr(main_module, "fetch_yfinance_symbol_daily_prices", lambda **_kwargs: [])
    yahoo_called = False

    def fake_fetch_kis_daily_prices(
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        is_adjusted: bool = False,
    ) -> list[dict[str, object]]:
        base_price = 10000 + int(symbol[-2:]) * 10
        return [
            {
                "symbol": symbol,
                "trade_date": (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
                "open": base_price + index,
                "high": base_price + index + 10,
                "low": base_price + index - 10,
                "close": base_price + index * 2,
                "adjusted_close": None,
                "volume": 100000 + index,
                "trading_value": (base_price + index * 2) * (100000 + index),
                "provider": "KIS Open API",
            }
            for index in range(40)
        ]

    def fake_fetch_yahoo_daily_prices(
        symbol: str,
        exchange: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        nonlocal yahoo_called
        yahoo_called = True
        return []

    monkeypatch.setattr(main_module, "fetch_kis_daily_prices", fake_fetch_kis_daily_prices)
    monkeypatch.setattr(main_module, "fetch_yahoo_daily_prices", fake_fetch_yahoo_daily_prices)

    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": "relative-momentum-swing",
            "start_year": 2026,
            "end_year": 2026,
            "initial_amount": 1000000,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["source"] == "daily-price-backtest:KIS Open API"
    assert data["rebalance_history"]
    assert yahoo_called is False


def test_backtest_run_unknown_strategy_returns_404() -> None:
    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": "unknown",
            "start_year": 2024,
            "end_year": 2025,
            "initial_amount": 10000000,
        },
    )

    assert response.status_code == 404


def test_user_strategy_lifecycle_uses_database(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)

    create_response = client.post(
        "/api/user-strategies",
        json={
            "name": "외국인 기관 수급 유입",
            "summary": "외국인과 기관이 함께 사는 후보",
            "formula": "외국인 5일 순매수 >= 500억 AND 기관 5일 순매수 >= 300억",
            "result_count": 7,
        },
    )
    created = create_response.json()

    assert create_response.status_code == 201
    assert created["code"].startswith("user-")
    assert created["name"] == "외국인 기관 수급 유입"
    assert created["result_count"] == 7

    list_response = client.get("/api/user-strategies")
    assert list_response.status_code == 200
    assert [item["code"] for item in list_response.json()] == [created["code"]]

    delete_response = client.delete(f"/api/user-strategies/{created['code']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    empty_response = client.get("/api/user-strategies")
    assert empty_response.status_code == 200
    assert empty_response.json() == []


def test_user_strategy_candidates_apply_saved_formula(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:10],
        start=date(2026, 1, 1),
        days=40,
    )

    create_response = client.post(
        "/api/user-strategies",
        json={
            "name": "삼성 키워드 전략",
            "summary": "검색식 키워드 필터 적용",
            "formula": 'keyword contains "삼성"',
            "result_count": 1,
        },
    )
    strategy_code = create_response.json()["code"]

    response = client.get(f"/api/strategies/{strategy_code}/candidates")
    data = response.json()

    assert response.status_code == 200
    assert data["source"] == "daily-price-candidates:Yahoo Finance:filtered"
    assert [item["symbol"] for item in data["candidates"]] == ["005930"]


def test_backtest_run_accepts_user_strategy(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)
    stub_empty_yahoo_prices(monkeypatch)

    create_response = client.post(
        "/api/user-strategies",
        json={
            "name": "검색식 저장 전략",
            "summary": "검색기에서 저장한 전략",
            "formula": "모멘텀 >= 70 AND 수급 점수 >= 80",
            "result_count": 5,
        },
    )
    strategy_code = create_response.json()["code"]

    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": strategy_code,
            "start_year": 2024,
            "end_year": 2025,
            "initial_amount": 10000000,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["strategy_code"] == strategy_code
    assert data["strategy_name"] == "검색식 저장 전략"
    assert len(data["equity_curve"]) == 24


def test_backtest_run_persists_recent_summary(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)
    stub_empty_yahoo_prices(monkeypatch)

    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": "trend-breakout",
            "start_year": 2024,
            "end_year": 2025,
            "initial_amount": 10000000,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert isinstance(data["run_id"], int)

    recent_response = client.get("/api/backtests/runs?limit=5")
    recent = recent_response.json()

    assert recent_response.status_code == 200
    assert recent[0]["id"] == data["run_id"]
    assert recent[0]["strategy_code"] == "trend-breakout"
    assert recent[0]["period"] == "2024 ~ 2025"
    assert recent[0]["initial_amount"] == 10000000
    assert recent[0]["final_amount"] == data["final_amount"]

    detail_response = client.get(f"/api/backtests/runs/{data['run_id']}")
    detail = detail_response.json()

    assert detail_response.status_code == 200
    assert detail["run_id"] == data["run_id"]
    assert detail["strategy_code"] == "trend-breakout"
    assert detail["equity_curve"] == data["equity_curve"]


def test_backtest_run_adds_selected_benchmark_curve(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)

    monkeypatch.setattr(main_module, "fetch_yahoo_daily_prices", lambda **_kwargs: [])

    def fake_fetch_yfinance_symbol_daily_prices(
        yahoo_symbol: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        assert yahoo_symbol == "^GSPC"
        return [
            {
                "symbol": yahoo_symbol,
                "trade_date": "2026-01-02",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "adjusted_close": 100.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": yahoo_symbol,
                "trade_date": "2026-01-30",
                "open": 100.0,
                "high": 111.0,
                "low": 99.0,
                "close": 110.0,
                "adjusted_close": 110.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": yahoo_symbol,
                "trade_date": "2026-02-02",
                "open": 110.0,
                "high": 112.0,
                "low": 108.0,
                "close": 110.0,
                "adjusted_close": 110.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": yahoo_symbol,
                "trade_date": "2026-02-27",
                "open": 110.0,
                "high": 122.0,
                "low": 109.0,
                "close": 121.0,
                "adjusted_close": 121.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
        ]

    monkeypatch.setattr(
        main_module,
        "fetch_yfinance_symbol_daily_prices",
        fake_fetch_yfinance_symbol_daily_prices,
    )

    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": "trend-breakout",
            "start_year": 2026,
            "end_year": 2026,
            "initial_amount": 1000000,
            "benchmark_code": "sp500",
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["benchmark_code"] == "sp500"
    assert data["benchmark_name"] == "S&P 500"
    assert data["benchmark_curve"] == [
        {"label": "2026.01", "benchmark": 1100000},
        {"label": "2026.02", "benchmark": 1210000},
    ]


def test_saved_backtest_refills_missing_benchmark_curve(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)

    def fake_fetch_yfinance_symbol_daily_prices(
        yahoo_symbol: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        assert yahoo_symbol == "^NDX"
        assert start == date(2026, 1, 1)
        assert end == date(2026, 12, 31)
        return [
            {
                "symbol": yahoo_symbol,
                "trade_date": "2026-01-02",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "adjusted_close": 100.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": yahoo_symbol,
                "trade_date": "2026-01-30",
                "open": 100.0,
                "high": 106.0,
                "low": 99.0,
                "close": 105.0,
                "adjusted_close": 105.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": yahoo_symbol,
                "trade_date": "2026-02-02",
                "open": 105.0,
                "high": 106.0,
                "low": 103.0,
                "close": 105.0,
                "adjusted_close": 105.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": yahoo_symbol,
                "trade_date": "2026-02-27",
                "open": 105.0,
                "high": 117.0,
                "low": 104.0,
                "close": 115.5,
                "adjusted_close": 115.5,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
        ]

    monkeypatch.setattr(
        main_module,
        "fetch_yfinance_symbol_daily_prices",
        fake_fetch_yfinance_symbol_daily_prices,
    )

    payload = {
        "strategy_code": "trend-breakout",
        "strategy_name": "추세 돌파형",
        "source": "sample-backtest-engine",
        "period": "2026 ~ 2026",
        "initial_amount": 1000000,
        "final_amount": 1120000,
        "run_at": "2026-06-21T09:00:00+09:00",
        "notice": "저장 테스트",
        "benchmark_code": "nasdaq100",
        "benchmark_name": "Nasdaq 100",
        "benchmark_curve": [],
        "metrics": [{"metric": "시작금액", "value": "1,000,000원"}],
        "annual_returns": [
            {
                "year": "2026",
                "portfolio_return": 12.0,
                "yield_pct": 0.0,
                "balance": 1120000,
                "income": 0,
            }
        ],
        "equity_curve": [{"label": "2026.01", "portfolio": 1120000}],
        "rebalance_history": [],
    }

    with session_factory() as session:
        run = BacktestRun(
            strategy_code="trend-breakout",
            strategy_name="추세 돌파형",
            source="sample-backtest-engine",
            start_year=2026,
            end_year=2026,
            initial_amount=1000000,
            final_amount=1120000,
            result_json=json.dumps(payload, ensure_ascii=False),
        )
        session.add(run)
        session.commit()
        run_id = run.id

    response = client.get(f"/api/backtests/runs/{run_id}")
    data = response.json()

    assert response.status_code == 200
    assert data["benchmark_code"] == "nasdaq100"
    assert data["benchmark_name"] == "Nasdaq 100"
    assert data["benchmark_curve"] == [
        {"label": "2026.01", "benchmark": 1050000},
        {"label": "2026.02", "benchmark": 1155000},
    ]


def test_data_status_returns_table_counts(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.counts = [1, 3, 0, 0, 0, 0, 0, 0, 2, 4]

        def __enter__(self) -> "FakeSession":
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            traceback: object,
        ) -> None:
            return None

        def scalar(self, _statement: object) -> int:
            return self.counts.pop(0)

    monkeypatch.setattr(main_module, "SessionLocal", FakeSession)

    response = client.get("/api/data/status")
    data = response.json()

    assert response.status_code == 200
    assert data["connected"] is True
    assert data["table_counts"]["markets"] == 1
    assert data["table_counts"]["instruments"] == 3
    assert data["table_counts"]["quote_snapshots"] == 0
    assert data["table_counts"]["supply_flow_dailies"] == 0
    assert data["table_counts"]["risk_indicator_dailies"] == 0
    assert data["table_counts"]["fundamental_ratios"] == 0
    assert data["table_counts"]["user_strategies"] == 2
    assert data["table_counts"]["backtest_runs"] == 4
    providers = {item["name"]: item for item in data["provider_status"]}
    assert providers["Yahoo Finance"]["ready"] is True
    assert providers["KIS Open API"]["status"] in {"App Key/Secret 필요", "인증정보 설정됨"}


def test_krx_instruments_preview_uses_market_data_provider(monkeypatch) -> None:
    def fake_fetch_krx_instruments(
        market: str,
        limit: int,
        base_date: str | None = None,
    ) -> list[dict[str, str]]:
        assert market == "KOSDAQ"
        assert limit == 2
        assert base_date == "20260619"
        return [
            {
                "symbol": "091990",
                "name": "셀트리온헬스케어",
                "exchange": "KOSDAQ",
                "asset_type": "stock",
            }
        ]

    monkeypatch.setattr(main_module, "fetch_krx_instruments", fake_fetch_krx_instruments)

    response = client.get("/api/data/krx/instruments?market=KOSDAQ&limit=2&base_date=20260619")
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == "KRX Open API"
    assert data["market"] == "KOSDAQ"
    assert data["base_date"] == "20260619"
    assert data["count"] == 1
    assert data["instruments"][0]["symbol"] == "091990"


def test_krx_instruments_preview_returns_503_when_provider_needs_permission(monkeypatch) -> None:
    def fake_fetch_krx_instruments(
        market: str,
        limit: int,
        base_date: str | None = None,
    ) -> list[dict[str, str]]:
        raise main_module.MarketDataProviderUnavailable("KRX 인증 정보 필요")

    monkeypatch.setattr(main_module, "fetch_krx_instruments", fake_fetch_krx_instruments)

    response = client.get("/api/data/krx/instruments?market=KOSPI&limit=1")

    assert response.status_code == 503
    assert response.json()["detail"] == "KRX 인증 정보 필요"


def test_kis_token_status_does_not_expose_token(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "get_kis_token_status",
        lambda: {
            "provider": "KIS Open API",
            "ready": True,
            "environment": "real",
            "base_url": "https://openapi.koreainvestment.com:9443",
            "token_cached": True,
            "expires_in_seconds": 3600,
        },
    )

    response = client.get("/api/data/kis/token/status")
    data = response.json()

    assert response.status_code == 200
    assert data["ready"] is True
    assert data["environment"] == "real"
    assert "access_token" not in data


def test_kis_current_price_uses_market_data_provider(monkeypatch) -> None:
    def fake_fetch_kis_current_price(symbol: str) -> dict[str, object]:
        assert symbol == "005930"
        return {
            "provider": "KIS Open API",
            "symbol": "005930",
            "name": "삼성전자",
            "price": 78000,
            "change": 1200,
            "change_rate": 1.56,
            "volume": 1234567,
            "trading_value": 98765432100,
            "open": 77000,
            "high": 78500,
            "low": 76500,
            "market_state": "정상",
        }

    monkeypatch.setattr(main_module, "fetch_kis_current_price", fake_fetch_kis_current_price)

    response = client.get("/api/data/kis/current-price?symbol=005930")
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == "KIS Open API"
    assert data["symbol"] == "005930"
    assert data["name"] == "삼성전자"
    assert data["price"] == 78000


def test_kis_market_cap_ranking_uses_market_data_provider(monkeypatch) -> None:
    def fake_fetch_kis_market_cap_ranking(limit: int = 50, market: str = "ALL") -> list[dict[str, object]]:
        assert limit == 2
        assert market == "KOSDAQ"
        return [
            {
                "provider": "KIS Open API",
                "symbol": "247540",
                "name": "에코프로비엠",
                "exchange": "KOSDAQ",
                "price": 132400,
                "change_rate": 4.1,
                "volume": 123456,
                "market_cap": 128000,
                "listed_shares": 1000000,
                "market_cap_weight": 1.2,
                "rank": 1,
            }
        ]

    monkeypatch.setattr(main_module, "fetch_kis_market_cap_ranking", fake_fetch_kis_market_cap_ranking)

    response = client.get("/api/data/kis/market-cap-ranking?market=KOSDAQ&limit=2")
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == "KIS Open API"
    assert data["count"] == 1
    assert data["items"][0]["symbol"] == "247540"
    assert data["items"][0]["exchange"] == "KOSDAQ"


def test_kis_investor_trade_daily_uses_market_data_provider(monkeypatch) -> None:
    def fake_fetch_kis_investor_trade_daily(
        symbol: str,
        base_date: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, object]]:
        assert symbol == "005930"
        assert base_date == date(2026, 6, 19)
        assert limit == 2
        return [
            {
                "provider": "KIS Open API",
                "symbol": "005930",
                "trade_date": "2026-06-19",
                "foreign_net_buy_qty": 1000,
                "institution_net_buy_qty": 500,
                "pension_net_buy_qty": 100,
                "foreign_net_buy_value": 1000000000,
                "institution_net_buy_value": 500000000,
                "pension_net_buy_value": 100000000,
                "individual_net_buy_value": -1600000000,
            }
        ]

    monkeypatch.setattr(main_module, "fetch_kis_investor_trade_daily", fake_fetch_kis_investor_trade_daily)

    response = client.get(
        "/api/data/kis/investor-trade-daily?symbol=005930&base_date=2026-06-19&limit=2"
    )
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == "KIS Open API"
    assert data["symbol"] == "005930"
    assert data["count"] == 1
    assert data["items"][0]["foreign_net_buy_value"] == 1000000000


def test_kis_daily_short_sale_uses_market_data_provider(monkeypatch) -> None:
    def fake_fetch_kis_daily_short_sale(
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, object]]:
        assert symbol == "005930"
        assert start == date(2026, 6, 1)
        assert end == date(2026, 6, 19)
        assert limit == 2
        return [
            {
                "provider": "KIS Open API",
                "symbol": "005930",
                "trade_date": "2026-06-19",
                "short_sale_volume": 1000,
                "short_sale_volume_ratio": 3.2,
                "short_sale_value": 800000000,
                "short_sale_value_ratio": 2.8,
            }
        ]

    monkeypatch.setattr(main_module, "fetch_kis_daily_short_sale", fake_fetch_kis_daily_short_sale)

    response = client.get(
        "/api/data/kis/daily-short-sale?symbol=005930&start=2026-06-01&end=2026-06-19&limit=2"
    )
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == "KIS Open API"
    assert data["count"] == 1
    assert data["items"][0]["short_sale_volume_ratio"] == 3.2


def test_kis_daily_credit_balance_uses_market_data_provider(monkeypatch) -> None:
    def fake_fetch_kis_daily_credit_balance(
        symbol: str,
        base_date: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, object]]:
        assert symbol == "005930"
        assert base_date == date(2026, 6, 19)
        assert limit == 2
        return [
            {
                "provider": "KIS Open API",
                "symbol": "005930",
                "trade_date": "2026-06-19",
                "margin_loan_balance": 100000000000,
                "margin_loan_balance_rate": 1.2,
                "margin_loan_new_amount": 12000000000,
                "margin_loan_redeem_amount": 8000000000,
                "stock_loan_balance": 1000000000,
                "stock_loan_balance_rate": 0.1,
            }
        ]

    monkeypatch.setattr(main_module, "fetch_kis_daily_credit_balance", fake_fetch_kis_daily_credit_balance)

    response = client.get("/api/data/kis/daily-credit-balance?symbol=005930&base_date=2026-06-19&limit=2")
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == "KIS Open API"
    assert data["count"] == 1
    assert data["items"][0]["margin_loan_balance"] == 100000000000


def test_kis_financial_ratios_uses_market_data_provider(monkeypatch) -> None:
    def fake_fetch_kis_financial_ratios(
        symbol: str,
        period_type: str = "annual",
        limit: int = 8,
    ) -> list[dict[str, object]]:
        assert symbol == "005930"
        assert period_type == "annual"
        assert limit == 2
        return [
            {
                "provider": "KIS Open API",
                "symbol": "005930",
                "fiscal_period": "202512",
                "period_type": "annual",
                "revenue_growth": 12.4,
                "operating_income_growth": 23.5,
                "net_income_growth": 34.6,
                "roe": 15.7,
                "eps": 4200,
                "sps": 120000,
                "bps": 80000,
                "reserve_ratio": 1200,
                "debt_ratio": 42.1,
            }
        ]

    monkeypatch.setattr(main_module, "fetch_kis_financial_ratios", fake_fetch_kis_financial_ratios)

    response = client.get("/api/data/kis/financial-ratios?symbol=005930&period_type=annual&limit=2")
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == "KIS Open API"
    assert data["period_type"] == "annual"
    assert data["count"] == 1
    assert data["items"][0]["roe"] == 15.7


def test_kis_access_token_reuses_file_cache(monkeypatch, tmp_path) -> None:
    token_path = tmp_path / "kis_token_cache.json"
    issue_count = 0

    monkeypatch.setenv("KIS_APP_KEY", "app-key")
    monkeypatch.setenv("KIS_APP_SECRET", "app-secret")
    monkeypatch.setenv("KIS_BASE_URL", "https://openapivts.koreainvestment.com:29443")
    monkeypatch.delenv("KIS_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("KIS_TOKEN_CACHE_PATH", str(token_path))
    market_data_module.KIS_TOKEN_CACHE.clear()

    def fake_issue_kis_access_token(
        *,
        app_key: str,
        app_secret: str,
        base_url: str,
    ) -> dict[str, object]:
        nonlocal issue_count
        issue_count += 1
        assert app_key == "app-key"
        assert app_secret == "app-secret"
        assert base_url == "https://openapivts.koreainvestment.com:29443"
        return {
            "access_token": "cached-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

    monkeypatch.setattr(market_data_module, "issue_kis_access_token", fake_issue_kis_access_token)

    assert market_data_module.get_kis_access_token() == "cached-token"
    market_data_module.KIS_TOKEN_CACHE.clear()
    assert market_data_module.get_kis_access_token() == "cached-token"
    assert issue_count == 1
    assert token_path.exists()


def test_kis_daily_prices_preview_uses_market_data_provider(monkeypatch) -> None:
    def fake_fetch_kis_daily_prices(
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        is_adjusted: bool = False,
    ) -> list[dict[str, object]]:
        assert symbol == "005930"
        assert start == date(2026, 6, 1)
        assert end == date(2026, 6, 5)
        assert is_adjusted is False
        return [
            {
                "symbol": symbol,
                "trade_date": "2026-06-03",
                "open": 70000.0,
                "high": 71000.0,
                "low": 69500.0,
                "close": 70500.0,
                "adjusted_close": None,
                "volume": 1000000,
                "trading_value": 70500000000,
                "provider": "KIS Open API",
            },
            {
                "symbol": symbol,
                "trade_date": "2026-06-04",
                "open": 70600.0,
                "high": 72000.0,
                "low": 70400.0,
                "close": 71800.0,
                "adjusted_close": None,
                "volume": 1200000,
                "trading_value": 86160000000,
                "provider": "KIS Open API",
            },
        ]

    monkeypatch.setattr(main_module, "fetch_kis_daily_prices", fake_fetch_kis_daily_prices)

    response = client.get(
        "/api/data/kis/daily-prices"
        "?symbol=005930&start=2026-06-01&end=2026-06-05&limit=1"
    )
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == "KIS Open API"
    assert data["symbol"] == "005930"
    assert data["count"] == 1
    assert data["prices"][0]["trade_date"] == "2026-06-04"


def test_kis_daily_prices_import_saves_daily_prices(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)

    def fake_fetch_kis_daily_prices(
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        is_adjusted: bool = False,
    ) -> list[dict[str, object]]:
        return [
            {
                "symbol": symbol,
                "trade_date": "2026-06-01",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 102.0,
                "adjusted_close": None,
                "volume": 1000,
                "trading_value": 102000,
                "provider": "KIS Open API",
            },
            {
                "symbol": symbol,
                "trade_date": "2026-06-30",
                "open": 102.0,
                "high": 110.0,
                "low": 101.0,
                "close": 108.0,
                "adjusted_close": None,
                "volume": 1200,
                "trading_value": 129600,
                "provider": "KIS Open API",
            },
        ]

    monkeypatch.setattr(main_module, "fetch_kis_daily_prices", fake_fetch_kis_daily_prices)

    response = client.post(
        "/api/data/kis/daily-prices/import",
        json={
            "symbol": "005930",
            "name": "삼성전자",
            "exchange": "KOSPI",
            "start": "2026-06-01",
            "end": "2026-06-30",
        },
    )
    data = response.json()

    assert response.status_code == 201
    assert data["provider"] == "KIS Open API"
    assert data["saved_count"] == 2

    with session_factory() as session:
        saved_count = session.scalar(select(func.count()).select_from(DailyPrice))
        provider_count = session.scalar(
            select(func.count()).select_from(DailyPrice).where(DailyPrice.provider == "KIS Open API")
        )
        assert saved_count == 2
        assert provider_count == 2


def test_yahoo_daily_prices_preview_uses_market_data_provider(monkeypatch) -> None:
    def fake_fetch_yahoo_daily_prices(
        symbol: str,
        exchange: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        assert symbol == "005930"
        assert exchange == "KOSPI"
        assert start == date(2026, 6, 1)
        assert end == date(2026, 6, 5)
        return [
            {
                "symbol": "005930.KS",
                "trade_date": "2026-06-03",
                "open": 70000.0,
                "high": 71000.0,
                "low": 69500.0,
                "close": 70500.0,
                "adjusted_close": 70500.0,
                "volume": 1000000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": "005930.KS",
                "trade_date": "2026-06-04",
                "open": 70600.0,
                "high": 72000.0,
                "low": 70400.0,
                "close": 71800.0,
                "adjusted_close": 71800.0,
                "volume": 1200000,
                "provider": "Yahoo Finance",
            },
        ]

    monkeypatch.setattr(main_module, "fetch_yahoo_daily_prices", fake_fetch_yahoo_daily_prices)

    response = client.get(
        "/api/data/yahoo/daily-prices"
        "?symbol=005930&exchange=KOSPI&start=2026-06-01&end=2026-06-05&limit=1"
    )
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == "Yahoo Finance"
    assert data["symbol"] == "005930"
    assert data["yahoo_symbol"] == "005930.KS"
    assert data["count"] == 1
    assert data["prices"][0]["trade_date"] == "2026-06-04"


def test_yahoo_daily_prices_preview_returns_400_for_invalid_period(monkeypatch) -> None:
    def fake_fetch_yahoo_daily_prices(
        symbol: str,
        exchange: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")

    monkeypatch.setattr(main_module, "fetch_yahoo_daily_prices", fake_fetch_yahoo_daily_prices)

    response = client.get(
        "/api/data/yahoo/daily-prices?symbol=005930&start=2026-06-05&end=2026-06-01"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "종료일은 시작일보다 빠를 수 없습니다."


def test_yahoo_strategy_batch_import_saves_daily_prices(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)

    def fake_fetch_yahoo_daily_prices(
        symbol: str,
        exchange: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        return [
            {
                "symbol": f"{symbol}.KS",
                "trade_date": "2026-06-01",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 102.0,
                "adjusted_close": 102.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": f"{symbol}.KS",
                "trade_date": "2026-06-30",
                "open": 102.0,
                "high": 110.0,
                "low": 101.0,
                "close": 108.0,
                "adjusted_close": 108.0,
                "volume": 1200,
                "provider": "Yahoo Finance",
            },
        ]

    monkeypatch.setattr(main_module, "fetch_yahoo_daily_prices", fake_fetch_yahoo_daily_prices)

    response = client.post(
        "/api/data/yahoo/daily-prices/import/strategy",
        json={
            "strategy_code": "relative-momentum-swing",
            "start": "2026-06-01",
            "end": "2026-06-30",
            "max_symbols": 2,
        },
    )
    data = response.json()

    assert response.status_code == 201
    assert data["success_count"] == 2
    assert data["failed_count"] == 0
    assert data["saved_count"] == 4

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(DailyPrice)) == 4


def test_backtest_run_uses_daily_prices_when_available(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)

    def fake_fetch_yahoo_daily_prices(
        symbol: str,
        exchange: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        return [
            {
                "symbol": f"{symbol}.KS",
                "trade_date": "2026-01-02",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "adjusted_close": 100.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": f"{symbol}.KS",
                "trade_date": "2026-01-30",
                "open": 100.0,
                "high": 111.0,
                "low": 99.0,
                "close": 110.0,
                "adjusted_close": 110.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": f"{symbol}.KS",
                "trade_date": "2026-02-02",
                "open": 110.0,
                "high": 112.0,
                "low": 108.0,
                "close": 110.0,
                "adjusted_close": 110.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": f"{symbol}.KS",
                "trade_date": "2026-02-27",
                "open": 110.0,
                "high": 122.0,
                "low": 109.0,
                "close": 121.0,
                "adjusted_close": 121.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
        ]

    monkeypatch.setattr(main_module, "fetch_yahoo_daily_prices", fake_fetch_yahoo_daily_prices)
    monkeypatch.setattr(main_module, "fetch_yfinance_symbol_daily_prices", lambda **_kwargs: [])

    import_response = client.post(
        "/api/data/yahoo/daily-prices/import/strategy",
        json={
            "strategy_code": "relative-momentum-swing",
            "start": "2026-01-01",
            "end": "2026-02-28",
            "max_symbols": 2,
        },
    )
    assert import_response.status_code == 201

    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": "relative-momentum-swing",
            "start_year": 2026,
            "end_year": 2026,
            "initial_amount": 1000000,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["source"] == "daily-price-backtest:Yahoo Finance"
    assert data["final_amount"] == 1100000
    assert len(data["equity_curve"]) == 1


def test_backtest_run_auto_imports_yahoo_prices_when_db_is_empty(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)

    def fake_fetch_yahoo_daily_prices(
        symbol: str,
        exchange: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        return [
            {
                "symbol": f"{symbol}.KS",
                "trade_date": "2026-01-02",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "adjusted_close": 100.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": f"{symbol}.KS",
                "trade_date": "2026-01-30",
                "open": 100.0,
                "high": 111.0,
                "low": 99.0,
                "close": 110.0,
                "adjusted_close": 110.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": f"{symbol}.KS",
                "trade_date": "2026-02-02",
                "open": 110.0,
                "high": 112.0,
                "low": 108.0,
                "close": 110.0,
                "adjusted_close": 110.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": f"{symbol}.KS",
                "trade_date": "2026-02-27",
                "open": 110.0,
                "high": 122.0,
                "low": 109.0,
                "close": 121.0,
                "adjusted_close": 121.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
        ]

    monkeypatch.setattr(main_module, "fetch_yahoo_daily_prices", fake_fetch_yahoo_daily_prices)
    monkeypatch.setattr(main_module, "fetch_yfinance_symbol_daily_prices", lambda **_kwargs: [])

    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": "relative-momentum-swing",
            "start_year": 2026,
            "end_year": 2026,
            "initial_amount": 1000000,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["source"] == "daily-price-backtest:Yahoo Finance"
    assert data["final_amount"] == 1100000


def test_backtest_run_ignores_incomplete_daily_price_symbols(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)

    def fake_fetch_yahoo_daily_prices(
        symbol: str,
        exchange: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        if symbol == "012450":
            return [
                {
                    "symbol": f"{symbol}.KS",
                    "trade_date": "2026-01-02",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0,
                    "adjusted_close": 100.0,
                    "volume": 1000,
                    "provider": "Yahoo Finance",
                },
                {
                    "symbol": f"{symbol}.KS",
                    "trade_date": "2026-01-30",
                    "open": 100.0,
                    "high": 111.0,
                    "low": 99.0,
                    "close": 110.0,
                    "adjusted_close": 110.0,
                    "volume": 1000,
                    "provider": "Yahoo Finance",
                },
                {
                    "symbol": f"{symbol}.KS",
                    "trade_date": "2026-02-02",
                    "open": 110.0,
                    "high": 112.0,
                    "low": 108.0,
                    "close": 110.0,
                    "adjusted_close": 110.0,
                    "volume": 1000,
                    "provider": "Yahoo Finance",
                },
                {
                    "symbol": f"{symbol}.KS",
                    "trade_date": "2026-02-27",
                    "open": 110.0,
                    "high": 122.0,
                    "low": 109.0,
                    "close": 121.0,
                    "adjusted_close": 121.0,
                    "volume": 1000,
                    "provider": "Yahoo Finance",
                },
            ]

        return [
            {
                "symbol": f"{symbol}.KQ",
                "trade_date": "2026-06-01",
                "open": 50.0,
                "high": 55.0,
                "low": 49.0,
                "close": 50.0,
                "adjusted_close": 50.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
            {
                "symbol": f"{symbol}.KQ",
                "trade_date": "2026-06-30",
                "open": 50.0,
                "high": 505.0,
                "low": 49.0,
                "close": 500.0,
                "adjusted_close": 500.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            },
        ]

    monkeypatch.setattr(main_module, "fetch_yahoo_daily_prices", fake_fetch_yahoo_daily_prices)
    monkeypatch.setattr(main_module, "fetch_yfinance_symbol_daily_prices", lambda **_kwargs: [])

    import_response = client.post(
        "/api/data/yahoo/daily-prices/import/strategy",
        json={
            "strategy_code": "relative-momentum-swing",
            "start": "2026-01-01",
            "end": "2026-06-30",
            "max_symbols": 2,
        },
    )
    assert import_response.status_code == 201

    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": "relative-momentum-swing",
            "start_year": 2026,
            "end_year": 2026,
            "initial_amount": 1000000,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["source"] == "daily-price-backtest:Yahoo Finance"
    assert data["final_amount"] == 1100000
    assert data["rebalance_history"][0]["holdings"] == "1종목"
    assert "한화에어로스페이스" in data["rebalance_history"][0]["entries"]
    assert "에코프로비엠" not in data["rebalance_history"][0]["entries"]
