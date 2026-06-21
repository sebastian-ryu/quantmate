from quantmate_api import providers


def test_provider_registry_groups_current_sources() -> None:
    registry = providers.build_provider_registry()

    assert registry.daily_price_provider_names() == (
        "KRX Open API",
        "KIS Open API",
        "Yahoo Finance",
    )
    assert [provider.name for provider in registry.instrument_providers] == [
        "KRX Open API",
        "KIS Open API",
    ]
    assert [provider.name for provider in registry.fundamental_providers] == ["KIS Open API"]
    assert [provider.name for provider in registry.broker_providers] == ["KIS 계좌"]
    assert [provider.name for provider in registry.status_providers] == [
        "KIS Open API",
        "KIS 계좌",
        "KIS WebSocket",
        "Yahoo Finance",
        "KRX Open API",
        "OpenDART",
    ]


def test_provider_status_rows_reflect_environment(monkeypatch) -> None:
    monkeypatch.setattr(providers, "is_kis_open_api_ready", lambda: True)
    monkeypatch.setattr(providers, "has_kis_account_credentials", lambda: True)
    monkeypatch.setattr(providers, "is_krx_open_api_ready", lambda: False)
    monkeypatch.setattr(
        providers,
        "get_kis_ws_approval_status",
        lambda: {"approval_key_cached": False},
    )
    monkeypatch.delenv("OPEN_DART_API_KEY", raising=False)

    rows = {row["name"]: row for row in providers.provider_status_rows()}

    assert rows["KIS Open API"]["ready"] is True
    assert rows["KIS 계좌"]["status"] == "계좌 설정됨"
    assert rows["KIS WebSocket"]["status"] == "App Key/Secret으로 접속키 발급 가능"
    assert rows["Yahoo Finance"]["ready"] is True
    assert rows["KRX Open API"]["status"] == "API 인증키 필요"
    assert rows["OpenDART"]["ready"] is False


def test_provider_status_rows_reflect_kis_websocket_cache(monkeypatch) -> None:
    monkeypatch.setattr(providers, "is_kis_open_api_ready", lambda: False)
    monkeypatch.setattr(
        providers,
        "get_kis_ws_approval_status",
        lambda: {"approval_key_cached": True},
    )

    rows = {row["name"]: row for row in providers.provider_status_rows()}

    assert rows["KIS WebSocket"]["ready"] is True
    assert rows["KIS WebSocket"]["status"] == "접속키 캐시됨"


def test_provider_status_rows_reflect_open_dart_key(monkeypatch) -> None:
    monkeypatch.setenv("OPEN_DART_API_KEY", "dart-test-key")

    rows = {row["name"]: row for row in providers.provider_status_rows()}

    assert rows["OpenDART"]["ready"] is True
    assert rows["OpenDART"]["status"] == "API 키 설정됨"
