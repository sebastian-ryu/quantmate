from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import quantmate_api.main as main_module

from quantmate_api.main import app
from quantmate_api.models import Base


client = TestClient(app)


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


def test_backtest_run_returns_monthly_equity_curve() -> None:
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


def test_data_status_returns_table_counts(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.counts = [1, 3, 0, 0, 2]

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
