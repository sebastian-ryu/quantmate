import json

import requests

import quantmate_api.market_data as market_data


def make_response(status_code: int, payload: dict[str, object]) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(payload).encode("utf-8")
    return response


def test_request_provider_response_retries_retryable_status(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setenv("MARKET_DATA_RETRY_COUNT", "1")
    monkeypatch.setenv("MARKET_DATA_RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("KIS_REQUEST_MIN_INTERVAL_SECONDS", "0")
    market_data.PROVIDER_LAST_REQUEST_AT.clear()

    def fake_request(*_args, **_kwargs) -> requests.Response:
        calls.append(1)
        if len(calls) == 1:
            return make_response(503, {"msg1": "temporary"})
        return make_response(200, {"rt_cd": "0"})

    monkeypatch.setattr(market_data.requests, "request", fake_request)

    response = market_data.request_provider_response(
        provider_key="kis",
        failure_label="KIS 테스트 호출 실패",
        method="GET",
        url="https://example.test",
    )

    assert response.status_code == 200
    assert len(calls) == 2


def test_request_provider_response_stops_after_retry_budget(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setenv("MARKET_DATA_RETRY_COUNT", "1")
    monkeypatch.setenv("MARKET_DATA_RETRY_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("KIS_REQUEST_MIN_INTERVAL_SECONDS", "0")
    market_data.PROVIDER_LAST_REQUEST_AT.clear()

    def fake_request(*_args, **_kwargs) -> requests.Response:
        calls.append(1)
        return make_response(503, {"msg1": "temporary"})

    monkeypatch.setattr(market_data.requests, "request", fake_request)

    response = market_data.request_provider_response(
        provider_key="kis",
        failure_label="KIS 테스트 호출 실패",
        method="GET",
        url="https://example.test",
    )

    assert response.status_code == 503
    assert len(calls) == 2
