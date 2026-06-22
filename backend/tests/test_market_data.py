import json
import zipfile
from datetime import date
from io import BytesIO

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


def test_normalize_yahoo_symbol_keeps_korea_suffix_behavior() -> None:
    assert market_data.normalize_yahoo_symbol("005930", "KOSPI") == "005930.KS"
    assert market_data.normalize_yahoo_symbol("035720", "KOSDAQ") == "035720.KQ"
    assert market_data.normalize_yahoo_symbol("005930.KS", "KOSPI") == "005930.KS"


def test_normalize_yahoo_symbol_supports_us_symbols_and_indexes() -> None:
    assert market_data.normalize_yahoo_symbol("AAPL", "NASDAQ") == "AAPL"
    assert market_data.normalize_yahoo_symbol("BRK.B", "NYSE") == "BRK-B"
    assert market_data.normalize_yahoo_symbol("^GSPC", "US") == "^GSPC"


def test_market_metadata_helpers_distinguish_kr_and_us_markets() -> None:
    assert market_data.normalize_market_code("KOSDAQ") == "KR"
    assert market_data.normalize_market_code("NYSE") == "US"
    assert market_data.market_currency("NASDAQ") == "USD"
    assert market_data.market_timezone("KOSPI") == "Asia/Seoul"
    assert market_data.market_timezone("US") == "America/New_York"


def test_call_krx_open_api_falls_back_from_portal_domain(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setenv("KRX_OPEN_API_AUTH_KEY", "test-key")
    monkeypatch.setenv("KRX_OPEN_API_BASE_URL", "https://openapi.krx.co.kr/svc/apis/sto")

    def fake_request_provider_response(**kwargs) -> requests.Response:
        calls.append(kwargs["url"])
        if "openapi.krx.co.kr" in kwargs["url"]:
            return make_response(404, {"message": "not found"})
        return make_response(200, {"OutBlock_1": [{"ISU_SRT_CD": "005930"}]})

    monkeypatch.setattr(market_data, "request_provider_response", fake_request_provider_response)

    payload = market_data.call_krx_open_api("/stk_isu_base_info", {"basDd": "20260619"})

    assert payload["OutBlock_1"][0]["ISU_SRT_CD"] == "005930"
    assert calls == [
        "https://openapi.krx.co.kr/svc/apis/sto/stk_isu_base_info",
        "https://data-dbg.krx.co.kr/svc/apis/sto/stk_isu_base_info",
    ]


def test_call_krx_open_api_reports_provider_response_message(monkeypatch) -> None:
    monkeypatch.setenv("KRX_OPEN_API_AUTH_KEY", "test-key")
    monkeypatch.delenv("KRX_OPEN_API_BASE_URL", raising=False)

    def fake_request_provider_response(**_kwargs) -> requests.Response:
        return make_response(401, {"respMsg": "Unauthorized API Call", "respCode": "401"})

    monkeypatch.setattr(market_data, "request_provider_response", fake_request_provider_response)

    try:
        market_data.call_krx_open_api("/stk_isu_base_info", {"basDd": "20260619"})
    except market_data.MarketDataProviderUnavailable as exc:
        assert str(exc) == "Unauthorized API Call (401)"
    else:
        raise AssertionError("KRX 권한 오류가 예외로 반환되어야 합니다.")


def test_fetch_krx_daily_prices_filters_symbol_and_normalizes_rows(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, str]]] = []
    monkeypatch.setenv("KRX_DAILY_PRICE_MAX_DAYS", "10")

    def fake_call_krx_open_api(endpoint: str, params: dict[str, str]) -> dict[str, object]:
        calls.append((endpoint, params))
        if params["basDd"] == "20260618":
            return {
                "OutBlock_1": [
                    {
                        "BAS_DD": "20260618",
                        "ISU_SRT_CD": "005930",
                        "ISU_ABBRV": "삼성전자",
                        "MKT_NM": "KOSPI",
                        "TDD_OPNPRC": "70,000",
                        "TDD_HGPRC": "71,000",
                        "TDD_LWPRC": "69,500",
                        "TDD_CLSPRC": "70,500",
                        "ACC_TRDVOL": "1,000,000",
                        "ACC_TRDVAL": "70,500,000,000",
                    },
                    {
                        "BAS_DD": "20260618",
                        "ISU_SRT_CD": "000660",
                        "ISU_ABBRV": "SK하이닉스",
                        "MKT_NM": "KOSPI",
                        "TDD_CLSPRC": "200,000",
                    },
                ]
            }
        return {
            "OutBlock_1": [
                {
                    "BAS_DD": "20260619",
                    "ISU_SRT_CD": "005930",
                    "ISU_ABBRV": "삼성전자",
                    "MKT_NM": "KOSPI",
                    "TDD_OPNPRC": "70,600",
                    "TDD_HGPRC": "72,000",
                    "TDD_LWPRC": "70,400",
                    "TDD_CLSPRC": "71,800",
                    "ACC_TRDVOL": "1,200,000",
                    "ACC_TRDVAL": "86,160,000,000",
                }
            ]
        }

    monkeypatch.setattr(market_data, "call_krx_open_api", fake_call_krx_open_api)

    rows = market_data.fetch_krx_daily_prices(
        symbol="005930",
        exchange="KOSPI",
        start=date(2026, 6, 18),
        end=date(2026, 6, 19),
    )

    assert calls == [
        ("/stk_bydd_trd", {"basDd": "20260618"}),
        ("/stk_bydd_trd", {"basDd": "20260619"}),
    ]
    assert rows == [
        {
            "symbol": "005930",
            "name": "삼성전자",
            "exchange": "KOSPI",
            "trade_date": "2026-06-18",
            "open": 70000.0,
            "high": 71000.0,
            "low": 69500.0,
            "close": 70500.0,
            "adjusted_close": None,
            "volume": 1000000,
            "trading_value": 70500000000,
            "provider": "KRX Open API",
        },
        {
            "symbol": "005930",
            "name": "삼성전자",
            "exchange": "KOSPI",
            "trade_date": "2026-06-19",
            "open": 70600.0,
            "high": 72000.0,
            "low": 70400.0,
            "close": 71800.0,
            "adjusted_close": None,
            "volume": 1200000,
            "trading_value": 86160000000,
            "provider": "KRX Open API",
        },
    ]


def test_fetch_krx_daily_prices_rejects_large_range(monkeypatch) -> None:
    monkeypatch.setenv("KRX_DAILY_PRICE_MAX_DAYS", "2")

    try:
        market_data.fetch_krx_daily_prices(
            symbol="005930",
            exchange="KOSPI",
            start=date(2026, 6, 1),
            end=date(2026, 6, 4),
        )
    except ValueError as exc:
        assert str(exc) == "KRX 일봉 조회 기간은 한 번에 최대 2일로 제한합니다."
    else:
        raise AssertionError("긴 KRX 일봉 조회 기간은 차단되어야 합니다.")


def test_parse_open_dart_corp_code_zip() -> None:
    content = BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr(
            "CORPCODE.xml",
            """
            <result>
              <list>
                <corp_code>00126380</corp_code>
                <corp_name>삼성전자</corp_name>
                <corp_eng_name>SAMSUNG ELECTRONICS CO,.LTD</corp_eng_name>
                <stock_code>005930</stock_code>
                <modify_date>20240630</modify_date>
              </list>
            </result>
            """,
        )

    rows = market_data.parse_open_dart_corp_code_zip(content.getvalue())

    assert rows == [
        {
            "corp_code": "00126380",
            "corp_name": "삼성전자",
            "corp_eng_name": "SAMSUNG ELECTRONICS CO,.LTD",
            "stock_code": "005930",
            "modify_date": "20240630",
        }
    ]


def test_int_from_open_dart_handles_common_amount_formats() -> None:
    assert market_data.int_from_open_dart("1,234,567") == 1234567
    assert market_data.int_from_open_dart("(1,234)") == -1234
    assert market_data.int_from_open_dart("-") is None


def test_summarize_open_dart_financial_statements_derives_ratios() -> None:
    rows = [
        {
            "account_id": "ifrs-full_Revenue",
            "account_name": "매출액",
            "current_amount": 1200,
            "previous_amount": 1000,
        },
        {
            "account_id": "dart_OperatingIncomeLoss",
            "account_name": "영업이익",
            "current_amount": 180,
            "previous_amount": 120,
        },
        {
            "account_id": "ifrs-full_ProfitLoss",
            "account_name": "당기순이익",
            "current_amount": 90,
            "previous_amount": 60,
        },
        {
            "account_id": "ifrs-full_Assets",
            "account_name": "자산총계",
            "current_amount": 2000,
        },
        {
            "account_id": "ifrs-full_EquityAndLiabilities",
            "account_name": "부채와자본총계",
            "current_amount": 2000,
        },
        {
            "account_id": "ifrs-full_Liabilities",
            "account_name": "부채총계",
            "current_amount": 800,
        },
        {
            "account_id": "ifrs-full_CurrentAssets",
            "account_name": "유동자산",
            "current_amount": 900,
        },
        {
            "account_id": "ifrs-full_CurrentLiabilities",
            "account_name": "유동부채",
            "current_amount": 450,
        },
        {
            "account_id": "ifrs-full_Equity",
            "account_name": "자본총계",
            "current_amount": 1200,
        },
        {
            "account_id": "ifrs-full_CashFlowsFromUsedInOperatingActivities",
            "account_name": "영업활동현금흐름",
            "current_amount": 150,
        },
        {
            "account_id": "dart_PurchaseOfPropertyPlantAndEquipment",
            "account_name": "유형자산의 취득",
            "current_amount": 40,
        },
        {
            "account_id": "ifrs-full_CashAndCashEquivalents",
            "account_name": "현금및현금성자산",
            "current_amount": 300,
        },
        {
            "account_id": "ifrs-full_DepreciationAndAmortizationExpense",
            "account_name": "감가상각비및무형자산상각비",
            "current_amount": 20,
        },
        {
            "account_id": "ifrs-full_DividendsPaidClassifiedAsFinancingActivities",
            "account_name": "배당금의 지급",
            "current_amount": -30,
            "previous_amount": -20,
        },
    ]

    summary = market_data.summarize_open_dart_financial_statements(rows)

    assert summary["revenue"] == 1200
    assert summary["revenue_growth"] == 20.0
    assert summary["operating_income_growth"] == 50.0
    assert summary["operating_margin"] == 15.0
    assert summary["net_margin"] == 7.5
    assert summary["debt_ratio"] == 66.67
    assert summary["current_ratio"] == 200.0
    assert summary["roe"] == 7.5
    assert summary["roa"] == 4.5
    assert summary["cash_and_cash_equivalents"] == 300
    assert summary["ebitda"] == 200
    assert summary["dividends_paid"] == 30
    assert summary["dividend_growth"] == 50.0
    assert summary["free_cash_flow"] == 110
