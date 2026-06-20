from fastapi.testclient import TestClient

import quantmate_api.main as main_module

from quantmate_api.main import app


client = TestClient(app)


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


def test_data_status_returns_table_counts(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.counts = [1, 3, 0, 0]

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
