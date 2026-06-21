import json
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import quantmate_api.main as main_module

from quantmate_api.main import app
from quantmate_api.models import BacktestRun, Base, DailyPrice


client = TestClient(app)


def stub_empty_yahoo_prices(monkeypatch) -> None:
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
            self.counts = [1, 3, 0, 0, 2, 4]

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
    assert data["final_amount"] == 1210000
    assert len(data["equity_curve"]) == 2


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
    assert data["final_amount"] == 1210000


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
    assert data["final_amount"] == 1210000
    assert data["rebalance_history"][0]["holdings"] == "1종목"
    assert "한화에어로스페이스" in data["rebalance_history"][0]["entries"]
    assert "에코프로비엠" not in data["rebalance_history"][0]["entries"]
