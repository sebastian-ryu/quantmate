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
    assert len(data["strategies"]) >= 3
    assert len(data["recommendations"]) >= 3
    assert data["backtest"]["metrics"]
    assert data["modes"][0]["code"] == "research"


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


def test_paper_config_toggle_updates_dashboard_mode() -> None:
    original_enabled = main_module.PAPER_CONFIG.enabled

    try:
        response = client.put("/api/paper/config", json={"enabled": False})
        assert response.status_code == 200
        assert response.json()["enabled"] is False

        dashboard_response = client.get("/api/dashboard")
        paper_mode = next(
            mode for mode in dashboard_response.json()["modes"] if mode["code"] == "paper"
        )
        assert paper_mode["enabled"] is False
    finally:
        main_module.PAPER_CONFIG.enabled = original_enabled
