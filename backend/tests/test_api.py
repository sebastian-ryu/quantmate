import json
import time
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import quantmate_api.main as main_module
import quantmate_api.market_data as market_data_module

from quantmate_api.kis_realtime import KisRealtimeStatus, parse_kis_realtime_quote
from quantmate_api.main import app
from quantmate_api.models import (
    BacktestRun,
    Base,
    BrokerAuditLog,
    DailyPrice,
    DataImportJob,
    FundamentalRatio,
    Instrument,
    Market,
    QuoteSnapshot,
    RiskIndicatorDaily,
    StrategySelectionRun,
    SupplyFlowDaily,
)
from quantmate_api.backtest_engine import build_daily_price_backtest
from quantmate_api.strategy_engine import (
    CANDIDATE_UNIVERSE,
    apply_user_strategy_formula,
    build_strategy_candidates_from_daily_prices,
)


client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_kis_auto_import_by_default(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: False)
    monkeypatch.setattr(main_module, "is_open_dart_ready", lambda: False)
    monkeypatch.delenv("DAILY_LOSS_STOP_ENABLED", raising=False)
    monkeypatch.delenv("EMERGENCY_STOP_ENABLED", raising=False)
    monkeypatch.delenv("MANUAL_ORDER_CONFIRMATION_REQUIRED", raising=False)
    main_module.STRATEGY_PERFORMANCE_CACHE["key"] = None
    main_module.STRATEGY_PERFORMANCE_CACHE["strategies"] = None

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


def seed_additional_daily_prices(
    session_factory: sessionmaker,
    *,
    symbols: list[dict[str, object]],
    provider: str,
    start: date,
    days: int,
) -> None:
    with session_factory() as session:
        instruments = {
            instrument.symbol: instrument
            for instrument in session.scalars(select(Instrument).where(Instrument.symbol.in_([str(item["symbol"]) for item in symbols])))
        }

        for symbol_index, item in enumerate(symbols):
            symbol = str(item["symbol"])
            instrument = instruments[symbol]
            base_price = 12000 + symbol_index * 1000
            drift = 1 + symbol_index * 0.12

            for day_index in range(days):
                trade_date = start + timedelta(days=day_index)
                close_price = base_price + day_index * drift * 8
                session.add(
                    DailyPrice(
                        instrument_id=instrument.id,
                        trade_date=trade_date,
                        open_price=close_price - 20,
                        high_price=close_price + 45,
                        low_price=close_price - 50,
                        close_price=close_price,
                        volume=90000 + symbol_index * 10000 + day_index * 90,
                        trading_value=close_price * (90000 + symbol_index * 10000 + day_index * 90),
                        provider=provider,
                        is_adjusted=False,
                    )
                )

        session.commit()


def make_price_rows(
    symbol: str,
    *,
    name: str,
    start_price: int,
    daily_step: int,
    volume: int,
    start: date = date(2026, 1, 1),
    days: int = 40,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(days):
        close_price = start_price + index * daily_step
        rows.append(
            {
                "symbol": symbol,
                "name": name,
                "exchange": "KOSPI",
                "trade_date": start + timedelta(days=index),
                "open_price": close_price - 10,
                "high_price": close_price + 20,
                "low_price": close_price - 20,
                "close_price": close_price,
                "volume": volume,
                "trading_value": close_price * volume,
                "provider": "Yahoo Finance",
            }
        )
    return rows


def test_health_endpoint() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["live_trading_enabled"] is False


def test_daily_price_provider_priority_uses_env(monkeypatch) -> None:
    monkeypatch.setenv("DAILY_PRICE_PROVIDER_PRIORITY", "Yahoo Finance,KIS Open API")

    assert main_module._daily_price_provider_priority() == [
        "Yahoo Finance",
        "KIS Open API",
        "KRX Open API",
    ]


def test_kis_broker_status_masks_account(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: True)
    monkeypatch.setattr(main_module, "has_kis_account_credentials", lambda: True)
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.setenv("KIS_ACCOUNT_NO", "12345678")
    monkeypatch.setenv("KIS_ACCOUNT_PRODUCT_CODE", "01")

    response = client.get("/api/broker/kis/account/status")
    data = response.json()

    assert response.status_code == 200
    assert data["ready"] is True
    assert data["environment"] == "paper"
    assert data["account_label"] == "******78-01"


def test_kis_broker_balance_logs_audit(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "get_kis_environment_name", lambda: "paper")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "12345678")
    monkeypatch.setenv("KIS_ACCOUNT_PRODUCT_CODE", "01")

    def fake_balance() -> dict[str, object]:
        return {
            "provider": "KIS Open API",
            "environment": "paper",
            "account_label": "******78-01",
            "fetched_at": "2026-06-21T10:00:00",
            "summary": {
                "deposit_amount": 1000000,
                "next_settlement_amount": 0,
                "purchase_amount": 500000,
                "evaluation_amount": 550000,
                "profit_loss_amount": 50000,
                "profit_loss_rate": 10.0,
                "securities_evaluation_amount": 550000,
                "total_evaluation_amount": 1550000,
                "net_asset_amount": 1550000,
                "total_loan_amount": 0,
                "previous_total_asset_evaluation_amount": 1500000,
                "asset_change_amount": 50000,
                "asset_change_rate": 3.33,
            },
            "holdings": [
                {
                    "symbol": "005930",
                    "name": "삼성전자",
                    "trade_type": "",
                    "holding_quantity": 10,
                    "orderable_quantity": 10,
                    "average_price": 50000,
                    "purchase_amount": 500000,
                    "current_price": 55000,
                    "evaluation_amount": 550000,
                    "profit_loss_amount": 50000,
                    "profit_loss_rate": 10.0,
                    "evaluation_earning_rate": 10.0,
                    "change_rate": 1.2,
                }
            ],
        }

    monkeypatch.setattr(main_module, "fetch_kis_domestic_balance", fake_balance)

    response = client.get("/api/broker/kis/balance")
    data = response.json()

    assert response.status_code == 200
    assert data["summary"]["net_asset_amount"] == 1550000
    assert data["holdings"][0]["name"] == "삼성전자"

    with session_factory() as session:
        log = session.scalar(select(BrokerAuditLog))
        assert log is not None
        assert log.action == "account_balance.read"
        assert "12345678" not in log.request_json


def test_kis_broker_orders_logs_audit(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "get_kis_environment_name", lambda: "paper")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "12345678")
    monkeypatch.setenv("KIS_ACCOUNT_PRODUCT_CODE", "01")

    def fake_orders(**_kwargs) -> dict[str, object]:
        return {
            "provider": "KIS Open API",
            "environment": "paper",
            "account_label": "******78-01",
            "start_date": "2026-06-07",
            "end_date": "2026-06-21",
            "summary": {
                "total_order_quantity": 1,
                "total_filled_quantity": 1,
                "total_filled_amount": 70000,
                "estimated_fee_total": 0,
                "purchase_average_price": 70000,
            },
            "orders": [
                {
                    "order_date": "2026-06-21",
                    "order_time": "10:10:10",
                    "order_branch_no": "001",
                    "order_no": "0000000001",
                    "original_order_no": "",
                    "symbol": "005930",
                    "name": "삼성전자",
                    "side_code": "02",
                    "side_name": "매수",
                    "order_type_name": "시장가",
                    "order_type_code": "01",
                    "ordered_quantity": 1,
                    "order_price": 0,
                    "filled_quantity": 1,
                    "average_price": 70000,
                    "filled_amount": 70000,
                    "remaining_quantity": 0,
                    "rejected_quantity": 0,
                    "canceled": False,
                    "status": "체결",
                    "execution_condition": "",
                    "exchange_code": "KRX",
                }
            ],
        }

    monkeypatch.setattr(main_module, "fetch_kis_daily_order_executions", fake_orders)

    response = client.get("/api/broker/kis/orders")
    data = response.json()

    assert response.status_code == 200
    assert data["orders"][0]["status"] == "체결"
    assert data["summary"]["total_filled_quantity"] == 1

    with session_factory() as session:
        log = session.scalar(select(BrokerAuditLog))
        assert log is not None
        assert log.action == "order_history.read"
        assert "12345678" not in log.request_json


def test_kis_paper_order_requires_enabled_flag(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.delenv("PAPER_TRADING_ENABLED", raising=False)

    response = client.post(
        "/api/broker/kis/paper/orders",
        json={"side": "buy", "symbol": "005930", "quantity": 1, "confirm_submit": True},
    )

    assert response.status_code == 403
    assert "PAPER_TRADING_ENABLED" in response.json()["detail"]


def test_kis_trading_safety_status_reports_env_limits(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: True)
    monkeypatch.setattr(main_module, "has_kis_account_credentials", lambda: True)
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.setattr(main_module, "get_kis_environment_name", lambda: "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "false")
    monkeypatch.setenv("EMERGENCY_STOP_ENABLED", "true")
    monkeypatch.setenv("MANUAL_ORDER_CONFIRMATION_REQUIRED", "false")
    monkeypatch.setenv("DAILY_LOSS_STOP_ENABLED", "true")
    monkeypatch.setenv("MAX_ORDER_AMOUNT_KRW", "123456")
    monkeypatch.setenv("MAX_DAILY_ORDER_COUNT", "7")
    monkeypatch.setenv("MAX_DAILY_LOSS_KRW", "90000")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "12345678")
    monkeypatch.setenv("KIS_ACCOUNT_PRODUCT_CODE", "01")

    response = client.get("/api/broker/kis/safety-status")
    data = response.json()

    assert response.status_code == 200
    assert data["environment"] == "paper"
    assert data["account_label"] == "******78-01"
    assert data["paper_trading_enabled"] is True
    assert data["emergency_stop_enabled"] is True
    assert data["manual_confirmation_required"] is False
    assert data["daily_loss_stop_enabled"] is True
    assert data["max_order_amount_krw"] == 123456
    assert data["max_daily_order_count"] == 7
    assert data["max_daily_loss_krw"] == 90000
    assert data["remaining_daily_order_count"] == 7
    assert data["can_submit_paper_orders"] is False
    assert any("긴급 중지" in warning for warning in data["warnings"])


def test_kis_paper_order_requires_confirm_phrase(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")

    response = client.post(
        "/api/broker/kis/paper/orders",
        json={
            "side": "buy",
            "symbol": "005930",
            "quantity": 1,
            "order_type": "limit",
            "price": 70000,
            "confirm_submit": True,
            "confirm_phrase": "실행",
        },
    )

    assert response.status_code == 400
    assert "확인 문구" in response.json()["detail"]


def test_kis_paper_batch_order_rejects_emergency_stop(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_STOP_ENABLED", "true")

    response = client.post(
        "/api/broker/kis/paper/orders/batch",
        json={
            "confirm_submit": True,
            "confirm_phrase": "모의주문 실행",
            "orders": [
                {
                    "symbol": "005930",
                    "name": "삼성전자",
                    "quantity": 1,
                    "order_type": "limit",
                    "price": 70000,
                }
            ],
        },
    )

    assert response.status_code == 423
    assert "EMERGENCY_STOP_ENABLED" in response.json()["detail"]


def test_kis_paper_batch_order_rejects_daily_loss_stop(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.setattr(main_module, "get_kis_environment_name", lambda: "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("DAILY_LOSS_STOP_ENABLED", "true")
    monkeypatch.setenv("MAX_DAILY_LOSS_KRW", "50000")

    def fake_balance() -> dict[str, object]:
        return {
            "provider": "KIS Open API",
            "environment": "paper",
            "account_label": "",
            "fetched_at": "2026-06-21T10:00:00",
            "summary": {
                "asset_change_amount": -60000,
                "net_asset_amount": 9940000,
                "previous_total_asset_evaluation_amount": 10000000,
            },
            "holdings": [],
        }

    monkeypatch.setattr(main_module, "fetch_kis_domestic_balance", fake_balance)

    response = client.post(
        "/api/broker/kis/paper/orders/batch",
        json={
            "confirm_submit": True,
            "confirm_phrase": "모의주문 실행",
            "orders": [
                {
                    "symbol": "005930",
                    "name": "삼성전자",
                    "quantity": 1,
                    "order_type": "limit",
                    "price": 70000,
                }
            ],
        },
    )

    assert response.status_code == 403
    assert "일일 손실 중지 한도" in response.json()["detail"]

    with session_factory() as session:
        log = session.scalar(select(BrokerAuditLog))
        assert log is not None
        assert log.action == "paper_batch_order.daily_loss_stop"
        assert log.status == "failed"


def test_kis_paper_order_logs_before_and_after(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.setattr(main_module, "get_kis_environment_name", lambda: "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "12345678")
    monkeypatch.setenv("KIS_ACCOUNT_PRODUCT_CODE", "01")

    def fake_submit_order(**kwargs) -> dict[str, object]:
        return {
            "provider": "KIS Open API",
            "environment": "paper",
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "order_type": kwargs["order_type"],
            "quantity": kwargs["quantity"],
            "price": 0,
            "order_no": "0000000001",
            "order_time": "101010",
            "exchange_order_org_no": "001",
            "message": "모의주문 접수",
        }

    monkeypatch.setattr(main_module, "submit_kis_domestic_cash_order", fake_submit_order)

    response = client.post(
        "/api/broker/kis/paper/orders",
        json={
            "side": "buy",
            "symbol": "005930",
            "quantity": 1,
            "order_type": "limit",
            "price": 70000,
            "confirm_submit": True,
            "confirm_phrase": "모의주문 실행",
        },
    )
    data = response.json()

    assert response.status_code == 202
    assert data["order_no"] == "0000000001"
    assert data["audit_log_id"] is not None

    with session_factory() as session:
        logs = session.scalars(select(BrokerAuditLog).order_by(BrokerAuditLog.id)).all()
        assert [log.action for log in logs] == ["paper_order.submit.before", "paper_order.submit.after"]
        assert all("12345678" not in log.request_json for log in logs)


def test_kis_paper_order_rejects_order_amount_limit(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.setattr(main_module, "get_kis_environment_name", lambda: "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("MAX_ORDER_AMOUNT_KRW", "50000")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "12345678")
    monkeypatch.setenv("KIS_ACCOUNT_PRODUCT_CODE", "01")
    submitted = False

    def fake_submit_order(**_kwargs) -> dict[str, object]:
        nonlocal submitted
        submitted = True
        return {}

    monkeypatch.setattr(main_module, "submit_kis_domestic_cash_order", fake_submit_order)

    response = client.post(
        "/api/broker/kis/paper/orders",
        json={
            "side": "buy",
            "symbol": "005930",
            "quantity": 1,
            "order_type": "limit",
            "price": 70000,
            "confirm_submit": True,
            "confirm_phrase": "모의주문 실행",
        },
    )

    assert response.status_code == 400
    assert "1회 주문 한도" in response.json()["detail"]
    assert submitted is False

    with session_factory() as session:
        log = session.scalar(select(BrokerAuditLog))
        assert log is not None
        assert log.action == "paper_order.risk_check"
        assert log.status == "failed"


def test_kis_order_proposal_builds_strategy_batch(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.setattr(main_module, "get_kis_environment_name", lambda: "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("MAX_ORDER_AMOUNT_KRW", "1000000")
    monkeypatch.setenv("MAX_DAILY_ORDER_COUNT", "10")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "12345678")
    monkeypatch.setenv("KIS_ACCOUNT_PRODUCT_CODE", "01")

    def fake_balance() -> dict[str, object]:
        return {
            "provider": "KIS Open API",
            "environment": "paper",
            "account_label": "******78-01",
            "fetched_at": "2026-06-21T10:00:00",
            "summary": {"deposit_amount": 5000000},
            "holdings": [],
        }

    monkeypatch.setattr(main_module, "fetch_kis_domestic_balance", fake_balance)

    response = client.post(
        "/api/broker/kis/order-proposals",
        json={
            "strategy_code": "relative-momentum-swing",
            "max_positions": 3,
            "amount_per_symbol": 500000,
            "order_type": "market",
            "cash_buffer_rate": 10,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["strategy_code"] == "relative-momentum-swing"
    assert data["executable_count"] == 3
    assert data["total_estimated_amount"] > 0
    assert data["cash_buffer_amount"] == 500000
    assert len(data["lines"]) == 3
    assert all(line["status"] == "주문 가능" for line in data["lines"])
    assert all(line["quantity"] >= 1 for line in data["lines"])

    with session_factory() as session:
        log = session.scalar(select(BrokerAuditLog))
        assert log is not None
        assert log.action == "order_proposal.create"
        assert "12345678" not in log.request_json


def test_kis_order_proposal_marks_amount_too_small(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.setattr(main_module, "get_kis_environment_name", lambda: "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("MAX_ORDER_AMOUNT_KRW", "1000000")

    def fake_balance() -> dict[str, object]:
        return {
            "provider": "KIS Open API",
            "environment": "paper",
            "account_label": "",
            "fetched_at": "2026-06-21T10:00:00",
            "summary": {"deposit_amount": 5000000},
            "holdings": [],
        }

    monkeypatch.setattr(main_module, "fetch_kis_domestic_balance", fake_balance)

    response = client.post(
        "/api/broker/kis/order-proposals",
        json={
            "strategy_code": "relative-momentum-swing",
            "max_positions": 1,
            "amount_per_symbol": 1000,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["executable_count"] == 0
    assert data["lines"][0]["status"] == "금액 부족"
    assert data["lines"][0]["estimated_amount"] == 0


def test_kis_paper_batch_order_requires_confirm_phrase(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")

    response = client.post(
        "/api/broker/kis/paper/orders/batch",
        json={
            "confirm_submit": True,
            "confirm_phrase": "실행",
            "orders": [
                {
                    "symbol": "005930",
                    "name": "삼성전자",
                    "quantity": 1,
                    "order_type": "limit",
                    "price": 70000,
                }
            ],
        },
    )

    assert response.status_code == 400
    assert "확인 문구" in response.json()["detail"]


def test_kis_paper_batch_order_logs_before_and_after(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.setattr(main_module, "get_kis_environment_name", lambda: "paper")
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("MAX_ORDER_AMOUNT_KRW", "1000000")
    monkeypatch.setenv("MAX_DAILY_ORDER_COUNT", "10")
    monkeypatch.setenv("KIS_ACCOUNT_NO", "12345678")
    monkeypatch.setenv("KIS_ACCOUNT_PRODUCT_CODE", "01")

    submitted_symbols: list[str] = []

    def fake_submit_order(**kwargs) -> dict[str, object]:
        submitted_symbols.append(kwargs["symbol"])
        return {
            "provider": "KIS Open API",
            "environment": "paper",
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "order_type": kwargs["order_type"],
            "quantity": kwargs["quantity"],
            "price": kwargs["price"],
            "order_no": f"000000000{len(submitted_symbols)}",
            "order_time": "101010",
            "exchange_order_org_no": "001",
            "message": "모의주문 접수",
        }

    monkeypatch.setattr(main_module, "submit_kis_domestic_cash_order", fake_submit_order)

    response = client.post(
        "/api/broker/kis/paper/orders/batch",
        json={
            "confirm_submit": True,
            "confirm_phrase": "모의주문 실행",
            "orders": [
                {
                    "symbol": "005930",
                    "name": "삼성전자",
                    "quantity": 1,
                    "order_type": "limit",
                    "price": 70000,
                },
                {
                    "symbol": "000660",
                    "name": "SK하이닉스",
                    "quantity": 1,
                    "order_type": "limit",
                    "price": 120000,
                },
            ],
        },
    )
    data = response.json()

    assert response.status_code == 202
    assert submitted_symbols == ["005930", "000660"]
    assert data["submitted_count"] == 2
    assert data["failed_count"] == 0
    assert data["status"] == "success"
    assert data["total_estimated_amount"] == 190000

    with session_factory() as session:
        logs = session.scalars(select(BrokerAuditLog).order_by(BrokerAuditLog.id)).all()
        assert [log.action for log in logs] == [
            "paper_batch_order.submit.before",
            "paper_batch_order.submit.after",
        ]
        assert all("12345678" not in log.request_json for log in logs)
        assert main_module._count_today_successful_paper_orders() == 2


def test_dashboard_contains_initial_mvp_data() -> None:
    response = client.get("/api/dashboard")
    data = response.json()

    assert response.status_code == 200
    assert len(data["strategies"]) >= 6
    assert len(data["recommendations"]) >= 3
    assert data["backtest"]["metrics"]
    assert data["modes"][0]["code"] == "research"
    assert all(mode["code"] != "paper" for mode in data["modes"])
    first_strategy = data["strategies"][0]
    assert "performance" in first_strategy
    assert first_strategy["performance"] is None
    assert len(first_strategy["summary"]) > 80


def test_dashboard_strategy_performance_uses_daily_price_backtest(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:20],
        start=date(2016, 1, 1),
        days=365 * 11,
    )

    response = client.get("/api/strategies/performance?refresh=true")
    data = response.json()
    strategy = next(item for item in data if item["strategy_code"] == "relative-momentum-swing")
    performance = strategy["performance"]
    windows = {item["years"]: item for item in performance["windows"]}

    assert response.status_code == 200
    assert performance["source"] == "daily-price-backtest:Yahoo Finance"
    assert performance["data_as_of"] is not None
    assert windows[1]["cagr"] is not None
    assert windows[1]["mdd"] is not None
    assert windows[10]["final_amount"] is not None


def test_strategy_candidates_returns_ranked_rows() -> None:
    response = client.get("/api/strategies/relative-momentum-swing/candidates")
    data = response.json()

    assert response.status_code == 200
    assert data["strategy_code"] == "relative-momentum-swing"
    assert len(data["candidates"]) >= 10
    scores = [item["strategy_score"] for item in data["candidates"]]
    assert scores == sorted(scores, reverse=True)
    assert data["candidates"][0]["rationale"]


def test_strategy_execution_contract_reports_shared_modes(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: True)
    monkeypatch.setattr(main_module, "has_kis_account_credentials", lambda: True)
    monkeypatch.setattr(main_module, "is_kis_paper_trading", lambda: True)
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")

    response = client.get("/api/strategies/relative-momentum-swing/contract")
    data = response.json()
    modes = {mode["code"]: mode for mode in data["modes"]}

    assert response.status_code == 200
    assert data["strategy_code"] == "relative-momentum-swing"
    assert data["provider_priority"] == ["KRX Open API", "KIS Open API", "Yahoo Finance"]
    assert data["backtest_policy"]["holding_count"] == 10
    assert data["backtest_policy"]["rebalance_label"] == "월 1회"
    assert modes["screen"]["enabled"] is True
    assert modes["backtest"]["endpoint"] == "/api/backtests/run"
    assert modes["paper-order-proposal"]["enabled"] is True
    assert modes["paper-order-submit"]["enabled"] is True
    assert modes["live-order-submit"]["enabled"] is False
    assert "MAX_ORDER_AMOUNT_KRW" in data["safety_controls"]


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
    assert data["data_freshness"]["latest_daily_price_date"] == "2026-02-09"
    assert data["data_freshness"]["expected_daily_price_date"] == main_module._expected_latest_daily_price_date().isoformat()
    assert data["data_freshness"]["daily_price_status"] == "stale"
    assert data["data_freshness"]["warnings"]
    assert data["data_freshness"]["daily_price_providers"] == ["Yahoo Finance"]
    assert len(data["candidates"]) == 10
    assert data["candidates"][0]["rationale"]
    assert [item["strategy_score"] for item in data["candidates"]] == sorted(
        [item["strategy_score"] for item in data["candidates"]],
        reverse=True,
    )


def test_strategy_candidate_run_is_saved_and_reloaded(monkeypatch) -> None:
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
    assert data["run_id"] is not None
    assert data["run_at"] is not None

    with session_factory() as session:
        run = session.scalar(select(StrategySelectionRun))

    assert run is not None
    assert run.strategy_code == "relative-momentum-swing"
    assert run.result_count == 10

    list_response = client.get("/api/strategy-runs?limit=5")
    runs = list_response.json()

    assert list_response.status_code == 200
    assert len(runs) == 1
    assert runs[0]["id"] == data["run_id"]
    assert runs[0]["top_candidates"]

    saved_response = client.get(f"/api/strategy-runs/{data['run_id']}")
    saved = saved_response.json()

    assert saved_response.status_code == 200
    assert saved["run_id"] == data["run_id"]
    assert [item["symbol"] for item in saved["candidates"]] == [
        item["symbol"] for item in data["candidates"]
    ]


def test_strategy_candidates_filter_low_liquidity_when_enough_alternatives() -> None:
    price_rows: list[dict[str, object]] = []
    price_rows.extend(
        make_price_rows(
            "LOW001",
            name="저유동성급등",
            start_price=1000,
            daily_step=80,
            volume=100,
        )
    )
    for index in range(10):
        price_rows.extend(
            make_price_rows(
                f"LIQ{index:03d}",
                name=f"유동성후보{index}",
                start_price=10000 + index * 100,
                daily_step=25 + index,
                volume=200000 + index * 10000,
            )
        )

    candidates = build_strategy_candidates_from_daily_prices(
        strategy_code="relative-momentum-swing",
        price_rows=price_rows,
        limit=10,
    )

    assert len(candidates) == 10
    assert "LOW001" not in {item["symbol"] for item in candidates}


def test_strategy_candidates_keep_low_liquidity_with_warning_when_pool_is_small() -> None:
    price_rows = make_price_rows(
        "LOW001",
        name="저유동성급등",
        start_price=1000,
        daily_step=80,
        volume=100,
    )

    candidates = build_strategy_candidates_from_daily_prices(
        strategy_code="relative-momentum-swing",
        price_rows=price_rows,
        limit=10,
    )

    assert [item["symbol"] for item in candidates] == ["LOW001"]
    assert "유동성 부족" in candidates[0]["risk_flags"]


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
                snapshot_date=main_module.today_kst(),
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
    assert samsung["price"] == 78000
    assert samsung["change_pct"] == 1.2
    assert samsung["trading_value_krw_100m"] == 780
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
    assert samsung["per"] == pytest.approx(2.47, abs=0.01)
    assert samsung["pbr"] == pytest.approx(0.13, abs=0.01)
    assert samsung["psr"] == pytest.approx(0.09, abs=0.01)
    assert samsung["net_margin"] == pytest.approx(3.5, abs=0.01)
    assert samsung["roa"] == pytest.approx(11.05, abs=0.01)
    assert "KIS 재무 지표로 성장성/수익성/밸류에이션을 보강" in samsung["rationale"]


def test_strategy_candidates_enrich_with_open_dart_fundamentals(monkeypatch) -> None:
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
                fiscal_period="202512",
                period_type="annual",
                provider=main_module.OPEN_DART_FUNDAMENTAL_PROVIDER,
                revenue_growth=20.0,
                operating_income_growth=50.0,
                net_income_growth=40.0,
                roe=7.5,
                roa=4.5,
                operating_margin=15.0,
                net_margin=7.5,
                fcf_yield=5.25,
                ev_ebitda=8.75,
                dividend_yield=2.4,
                payout_ratio=30.0,
                current_ratio=180.0,
                dividend_growth=12.0,
                dividends_paid=30.0,
                dividend_streak_years=1,
                dividend_stability_score=78,
                eps=None,
                sps=None,
                bps=None,
                reserve_ratio=None,
                debt_ratio=66.67,
            )
        )
        session.add(
            FundamentalRatio(
                instrument_id=instrument.id,
                fiscal_period="202412",
                period_type="annual",
                provider=main_module.OPEN_DART_FUNDAMENTAL_PROVIDER,
                dividends_paid=20.0,
                debt_ratio=70.0,
            )
        )
        session.commit()

    response = client.get("/api/strategies/relative-momentum-swing/candidates")
    data = response.json()
    samsung = next(item for item in data["candidates"] if item["symbol"] == "005930")

    assert response.status_code == 200
    assert "OpenDART 재무" in data["source"]
    assert samsung["revenue_growth"] == 20.0
    assert samsung["operating_income_growth"] == 50.0
    assert samsung["eps_growth"] == 40.0
    assert samsung["roe"] == 7.5
    assert samsung["roa"] == 4.5
    assert samsung["operating_margin"] == 15.0
    assert samsung["net_margin"] == 7.5
    assert samsung["fcf_yield"] == 5.25
    assert samsung["ev_ebitda"] == 8.75
    assert samsung["dividend_yield"] == 2.4
    assert samsung["payout_ratio"] == 30.0
    assert samsung["current_ratio"] == 180.0
    assert samsung["dividend_growth"] == 12.0
    assert samsung["dividend_streak_years"] == 2
    assert samsung["dividend_stability_score"] == 78
    assert samsung["debt_ratio"] == 66.67
    assert "OpenDART 재무 지표로 성장성/수익성/밸류에이션을 보강" in samsung["rationale"]


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


def test_strategy_candidates_can_skip_auto_import_when_refresh_false(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: True)
    kis_daily_called = False

    def fake_fetch_kis_daily_prices(
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        is_adjusted: bool = False,
    ) -> list[dict[str, object]]:
        nonlocal kis_daily_called
        kis_daily_called = True
        return []

    monkeypatch.setattr(main_module, "fetch_kis_daily_prices", fake_fetch_kis_daily_prices)

    response = client.get("/api/strategies/relative-momentum-swing/candidates?refresh=false")
    data = response.json()

    assert response.status_code == 200
    assert data["source"] == "sample-engine"
    assert len(data["candidates"]) >= 10
    assert kis_daily_called is False


def test_strategy_candidates_default_auto_imports_latest_data(monkeypatch) -> None:
    use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: True)
    kis_daily_called = False

    def fake_fetch_kis_daily_prices(
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        is_adjusted: bool = False,
    ) -> list[dict[str, object]]:
        nonlocal kis_daily_called
        kis_daily_called = True
        base_price = 10000 + int(symbol[-2:]) * 10
        start_day = main_module.today_kst() - timedelta(days=39)
        return [
            {
                "symbol": symbol,
                "trade_date": (start_day + timedelta(days=index)).isoformat(),
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

    monkeypatch.setattr(main_module, "fetch_kis_daily_prices", fake_fetch_kis_daily_prices)

    response = client.get("/api/strategies/relative-momentum-swing/candidates")
    data = response.json()

    assert response.status_code == 200
    assert data["source"] == "daily-price-candidates:KIS Open API"
    assert data["data_freshness"]["daily_price_status"] == "current"
    assert len(data["candidates"]) >= 10
    assert kis_daily_called is True


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

    response = client.get("/api/strategies/relative-momentum-swing/candidates?refresh=true")
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
        start_day = main_module.today_kst() - timedelta(days=39)
        return [
            {
                "symbol": symbol,
                "trade_date": (start_day + timedelta(days=index)).isoformat(),
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

    response = client.get("/api/strategies/relative-momentum-swing/candidates?refresh=true")
    data = response.json()

    assert response.status_code == 200
    assert data["source"] == "daily-price-candidates:KIS Open API"
    assert len(data["candidates"]) >= 10
    assert yahoo_called is False


def test_screener_search_applies_formula_on_server(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "_auto_import_yahoo_daily_prices_for_strategy_candidates_if_needed", lambda *_args, **_kwargs: None)
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
    assert data["data_freshness"]["latest_daily_price_date"] == "2026-02-09"
    assert data["data_freshness"]["daily_price_status"] == "stale"
    assert data["data_freshness"]["daily_price_providers"] == ["Yahoo Finance"]
    assert data["unsupported_conditions"] == []
    assert [item["symbol"] for item in data["candidates"]] == ["005930"]


def test_screener_search_refreshes_current_quote_for_visible_rows(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "_auto_import_yahoo_daily_prices_for_strategy_candidates_if_needed", lambda *_args, **_kwargs: None)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:10],
        start=date(2026, 1, 1),
        days=40,
    )
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: True)

    def fake_fetch_kis_current_price(symbol: str) -> dict[str, object]:
        return {
            "provider": "KIS Open API",
            "symbol": symbol,
            "name": "삼성전자" if symbol == "005930" else symbol,
            "price": 78000 if symbol == "005930" else 50000,
            "change": 1200,
            "change_rate": 1.56 if symbol == "005930" else 0.1,
            "volume": 1234567,
            "trading_value": 98765432100,
            "open": 77000,
            "high": 78500,
            "low": 76500,
            "market_state": "정상",
        }

    monkeypatch.setattr(main_module, "fetch_kis_current_price", fake_fetch_kis_current_price)

    response = client.post(
        "/api/screener/search",
        json={
            "strategy_code": "relative-momentum-swing",
            "formula": 'keyword contains "삼성"',
            "limit": 20,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert "KIS 현재가" in data["source"]
    assert [item["symbol"] for item in data["candidates"]] == ["005930"]
    assert data["candidates"][0]["price"] == 78000
    assert data["candidates"][0]["change_pct"] == 1.56
    assert data["candidates"][0]["trading_value_krw_100m"] == 987.65


def test_user_strategy_formula_accepts_korean_numeric_conditions() -> None:
    candidates = [
        {
            "symbol": "005930",
            "name": "삼성전자",
            "foreign_net_buy_5d": 600,
            "institution_net_buy_5d": 350,
            "momentum": 72,
            "supply_score": 84,
        },
        {
            "symbol": "000660",
            "name": "SK하이닉스",
            "foreign_net_buy_5d": 450,
            "institution_net_buy_5d": 500,
            "momentum": 80,
            "supply_score": 90,
        },
    ]

    filtered, unsupported = apply_user_strategy_formula(
        candidates=candidates,
        formula="외국인 5일 순매수 >= 500억 AND 기관 5일 순매수 >= 300억 AND 모멘텀 >= 70",
    )

    assert unsupported == []
    assert [item["symbol"] for item in filtered] == ["005930"]


def test_strategy_candidates_unknown_strategy_returns_404() -> None:
    response = client.get("/api/strategies/unknown/candidates")

    assert response.status_code == 404


def test_backtest_run_rejects_year_before_krx_supported_range() -> None:
    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": "relative-momentum-swing",
            "start_year": 2009,
            "end_year": 2010,
            "initial_amount": 10000000,
        },
    )

    assert response.status_code == 422


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
    assert data["backtest_policy"]["holding_count"] == 10
    assert data["backtest_policy"]["initial_rebalance_amount"] == 1000000
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


def test_backtest_run_accepts_rebalance_and_holding_parameters(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:20],
        start=date(2025, 1, 1),
        days=470,
    )
    stub_empty_yahoo_prices(monkeypatch)

    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": "relative-momentum-swing",
            "start_year": 2026,
            "end_year": 2026,
            "initial_amount": 10000000,
            "rebalance_interval_months": 3,
            "holding_count": 5,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["backtest_policy"]["rebalance_interval_months"] == 3
    assert data["backtest_policy"]["rebalance_label"] == "분기 1회"
    assert data["backtest_policy"]["holding_count"] == 5
    assert data["backtest_policy"]["initial_rebalance_amount"] == 2000000
    assert "상위 5개" in data["notice"]
    assert "분기 1회" in data["notice"]
    assert {row["holdings"] for row in data["rebalance_history"]} == {"5종목"}


def test_daily_price_backtest_uses_strategy_parameters() -> None:
    price_rows: list[dict[str, object]] = []
    for index in range(25):
        price_rows.extend(
            make_price_rows(
                f"T{index:05d}",
                name=f"테스트후보{index}",
                start_price=10000 + index * 100,
                daily_step=8 + index,
                volume=200000 + index * 1000,
                start=date(2025, 1, 1),
                days=470,
            )
        )

    result = build_daily_price_backtest(
        strategy_code="value-quality-factor",
        strategy_name="가치/퀄리티 팩터",
        start_year=2026,
        end_year=2026,
        initial_amount=10_000_000,
        price_rows=price_rows,
        provider="테스트 제공처",
    )

    assert result is not None
    assert "상위 20개" in result["notice"]
    assert "분기 1회" in result["notice"]
    assert "거래비용 0.20%" in result["notice"]
    assert result["backtest_policy"]["holding_count"] == 20
    assert result["backtest_policy"]["rebalance_interval_months"] == 3
    assert result["backtest_policy"]["initial_rebalance_amount"] == 500000
    assert result["rebalance_history"]
    assert len(result["rebalance_history"]) < len(result["equity_curve"])
    assert {row["holdings"] for row in result["rebalance_history"]} == {"20종목"}


def test_daily_price_backtest_pads_curve_from_requested_start_year() -> None:
    price_rows: list[dict[str, object]] = []
    for index in range(12):
        price_rows.extend(
            make_price_rows(
                f"P{index:05d}",
                name=f"지연후보{index}",
                start_price=10000 + index * 100,
                daily_step=8 + index,
                volume=200000 + index * 1000,
                start=date(2025, 8, 1),
                days=90,
            )
        )

    result = build_daily_price_backtest(
        strategy_code="relative-momentum-swing",
        strategy_name="상대 모멘텀 스윙",
        start_year=2023,
        end_year=2026,
        initial_amount=10_000_000,
        price_rows=price_rows,
        provider="테스트 제공처",
    )

    assert result is not None
    assert result["equity_curve"][0] == {"label": "2023.01", "portfolio": 10_000_000}
    assert result["equity_curve"][1] == {"label": "2023.02", "portfolio": 10_000_000}
    assert result["equity_curve"][31] == {"label": "2025.08", "portfolio": 10_000_000}
    assert result["equity_curve"][32]["label"] == "2025.09"
    assert result["annual_returns"][0]["year"] == "2023"
    assert result["annual_returns"][0]["portfolio_return"] == 0.0


def test_daily_price_backtest_starts_requested_period_at_initial_amount() -> None:
    price_rows: list[dict[str, object]] = []
    for index in range(12):
        price_rows.extend(
            make_price_rows(
                f"S{index:05d}",
                name=f"시작후보{index}",
                start_price=10000 + index * 100,
                daily_step=8 + index,
                volume=200000 + index * 1000,
                start=date(2020, 1, 1),
                days=760,
            )
        )

    result = build_daily_price_backtest(
        strategy_code="relative-momentum-swing",
        strategy_name="상대 모멘텀 스윙",
        start_year=2021,
        end_year=2022,
        initial_amount=10_000_000,
        price_rows=price_rows,
        provider="테스트 제공처",
    )

    assert result is not None
    assert result["equity_curve"][0] == {"label": "2021.01", "portfolio": 10_000_000}
    assert result["equity_curve"][1]["label"] == "2021.02"
    assert result["equity_curve"][1]["portfolio"] != 10_000_000


def test_backtest_run_prefers_provider_with_longer_period_coverage(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    symbols = CANDIDATE_UNIVERSE[:10]
    seed_daily_prices(
        session_factory,
        symbols=symbols,
        provider="Yahoo Finance",
        start=date(2022, 1, 1),
        days=1700,
    )
    seed_additional_daily_prices(
        session_factory,
        symbols=symbols,
        provider="KIS Open API",
        start=date(2025, 8, 1),
        days=330,
    )
    stub_empty_yahoo_prices(monkeypatch)

    response = client.post(
        "/api/backtests/run",
        json={
            "strategy_code": "relative-momentum-swing",
            "start_year": 2023,
            "end_year": 2026,
            "initial_amount": 10000000,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["source"] == "daily-price-backtest:Yahoo Finance"
    assert data["rebalance_history"][0]["date"] == "2023-01"
    assert data["equity_curve"][0]["label"] == "2023.01"
    assert data["equity_curve"][0]["portfolio"] == data["initial_amount"]
    assert data["equity_curve"][1]["portfolio"] != data["initial_amount"]


def test_backtest_run_uses_kis_without_yahoo_when_kis_covers_period(monkeypatch) -> None:
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
                "trade_date": (date(2025, 1, 1) + timedelta(days=index)).isoformat(),
                "open": base_price + index,
                "high": base_price + index + 10,
                "low": base_price + index - 10,
                "close": base_price + index * 2,
                "adjusted_close": None,
                "volume": 100000 + index,
                "trading_value": (base_price + index * 2) * (100000 + index),
                "provider": "KIS Open API",
            }
            for index in range(540)
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
    assert detail["backtest_policy"] == data["backtest_policy"]


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
        {"label": "2026.01", "benchmark": 1000000},
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
        {"label": "2026.01", "benchmark": 1000000},
        {"label": "2026.02", "benchmark": 1155000},
    ]
    assert data["backtest_policy"]["holding_count"] == 10
    assert data["backtest_policy"]["initial_rebalance_amount"] == 100000


def test_data_status_returns_table_counts(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.counts = [1, 3, 0, 0, 0, 0, 0, 5, 0, 2, 4, 6]

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
    assert data["table_counts"]["broker_audit_logs"] == 5
    assert data["table_counts"]["user_strategies"] == 2
    assert data["table_counts"]["backtest_runs"] == 4
    assert data["table_counts"]["strategy_selection_runs"] == 6
    providers = {item["name"]: item for item in data["provider_status"]}
    assert providers["Yahoo Finance"]["ready"] is True
    assert providers["KIS Open API"]["status"] in {"App Key/Secret 필요", "인증정보 설정됨"}
    assert providers["KIS 계좌"]["status"] in {"계좌번호 설정 필요", "계좌 설정됨"}


def test_data_quality_reports_price_coverage(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=CANDIDATE_UNIVERSE[:10],
        start=main_module.today_kst() - timedelta(days=39),
        days=40,
    )

    response = client.get("/api/data/quality")
    data = response.json()
    checks = {item["code"]: item for item in data["checks"]}

    assert response.status_code == 200
    assert data["summary_status"] == "warning"
    assert checks["daily-price-coverage"]["status"] == "ok"
    assert checks["daily-price-coverage"]["value"] == "10개 종목"
    assert checks["ohlcv-validity"]["status"] == "ok"
    assert checks["provider-mix"]["status"] == "ok"


def test_market_calendar_endpoint_returns_us_holidays() -> None:
    response = client.get("/api/data/market-calendar?market=NASDAQ&start=2026-06-18&end=2026-06-22")
    data = response.json()

    assert response.status_code == 200
    assert data["market"] == "US"
    assert data["timezone"] == "America/New_York"
    assert data["open_days"] == 2
    assert data["closed_days"] == 3
    assert data["items"][1]["date"] == "2026-06-19"
    assert data["items"][1]["reason"] == "Juneteenth National Independence Day"


def test_open_dart_corp_code_status_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "get_open_dart_corp_code_cache_status",
        lambda: {
            "provider": "OpenDART",
            "ready": True,
            "base_url": "https://opendart.fss.or.kr/api",
            "cache_path": "/tmp/opendart_corp_codes.json",
            "cached": True,
            "cached_count": 1,
            "fetched_at": "2026-06-21T12:00:00",
        },
    )

    response = client.get("/api/data/opendart/corp-codes/status")
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == "OpenDART"
    assert data["cached_count"] == 1


def test_open_dart_corp_code_cache_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "fetch_open_dart_corp_codes",
        lambda force_refresh=False: [
            {
                "corp_code": "00126380",
                "corp_name": "삼성전자",
                "corp_eng_name": "SAMSUNG ELECTRONICS CO,.LTD",
                "stock_code": "005930",
                "modify_date": "20240630",
            },
            {
                "corp_code": "00401731",
                "corp_name": "비상장테스트",
                "corp_eng_name": "",
                "stock_code": "",
                "modify_date": "20240630",
            },
        ],
    )
    monkeypatch.setattr(
        main_module,
        "get_open_dart_corp_code_cache_status",
        lambda: {
            "provider": "OpenDART",
            "ready": True,
            "base_url": "https://opendart.fss.or.kr/api",
            "cache_path": "/tmp/opendart_corp_codes.json",
            "cached": True,
            "cached_count": 2,
            "fetched_at": "2026-06-21T12:00:00",
        },
    )

    response = client.post("/api/data/opendart/corp-codes/cache?force_refresh=true")
    data = response.json()

    assert response.status_code == 201
    assert data["fetched_count"] == 2
    assert data["listed_count"] == 1
    assert data["cache_path"] == "/tmp/opendart_corp_codes.json"


def test_open_dart_financial_statements_endpoint(monkeypatch) -> None:
    def fake_fetch_open_dart_financial_statements(
        *,
        symbol: str,
        business_year: int,
        report_code: str = "11011",
        fs_div: str = "CFS",
        force_refresh_corp_codes: bool = False,
    ) -> list[dict[str, object]]:
        assert symbol == "005930"
        assert business_year == 2025
        assert report_code == "11011"
        assert fs_div == "CFS"
        assert force_refresh_corp_codes is False
        return [
            {
                "provider": "OpenDART",
                "symbol": "005930",
                "corp_code": "00126380",
                "corp_name": "삼성전자",
                "business_year": 2025,
                "report_code": "11011",
                "fs_div": "CFS",
                "receipt_no": "20260301000001",
                "statement_type": "IS",
                "statement_name": "손익계산서",
                "account_id": "ifrs-full_Revenue",
                "account_name": "매출액",
                "account_detail": "",
                "current_term_name": "제57기",
                "current_amount": 300000000000000,
                "current_accumulated_amount": None,
                "previous_term_name": "제56기",
                "previous_amount": 280000000000000,
                "previous_accumulated_amount": None,
                "currency": "KRW",
            }
        ]

    monkeypatch.setattr(main_module, "fetch_open_dart_financial_statements", fake_fetch_open_dart_financial_statements)

    response = client.get(
        "/api/data/opendart/financial-statements"
        "?symbol=005930&business_year=2025&report_code=11011&fs_div=CFS"
    )
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == "OpenDART"
    assert data["count"] == 1
    assert data["items"][0]["account_id"] == "ifrs-full_Revenue"
    assert data["summary"]["revenue"] == 300000000000000


def test_import_open_dart_financial_statements_saves_summary(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)

    def fake_fetch_open_dart_financial_statements(
        *,
        symbol: str,
        business_year: int,
        report_code: str = "11011",
        fs_div: str = "CFS",
        force_refresh_corp_codes: bool = False,
    ) -> list[dict[str, object]]:
        assert symbol == "005930"
        assert business_year == 2025
        assert report_code == "11011"
        assert fs_div == "CFS"
        assert force_refresh_corp_codes is False
        base = {
            "provider": "OpenDART",
            "symbol": "005930",
            "corp_code": "00126380",
            "corp_name": "삼성전자",
            "business_year": 2025,
            "report_code": "11011",
            "fs_div": "CFS",
            "receipt_no": "20260301000001",
            "statement_name": "테스트 재무제표",
            "account_detail": "",
            "current_term_name": "제57기",
            "current_accumulated_amount": None,
            "previous_term_name": "제56기",
            "previous_accumulated_amount": None,
            "currency": "KRW",
        }
        return [
            {
                **base,
                "statement_type": "IS",
                "account_id": "ifrs-full_Revenue",
                "account_name": "매출액",
                "current_amount": 1200,
                "previous_amount": 1000,
            },
            {
                **base,
                "statement_type": "IS",
                "account_id": "dart_OperatingIncomeLoss",
                "account_name": "영업이익",
                "current_amount": 180,
                "previous_amount": 120,
            },
            {
                **base,
                "statement_type": "IS",
                "account_id": "ifrs-full_ProfitLoss",
                "account_name": "당기순이익",
                "current_amount": 90,
                "previous_amount": 60,
            },
            {
                **base,
                "statement_type": "BS",
                "account_id": "ifrs-full_Assets",
                "account_name": "자산총계",
                "current_amount": 2000,
                "previous_amount": 1800,
            },
            {
                **base,
                "statement_type": "BS",
                "account_id": "ifrs-full_EquityAndLiabilities",
                "account_name": "부채와자본총계",
                "current_amount": 2000,
                "previous_amount": 1800,
            },
            {
                **base,
                "statement_type": "BS",
                "account_id": "ifrs-full_Liabilities",
                "account_name": "부채총계",
                "current_amount": 800,
                "previous_amount": 700,
            },
            {
                **base,
                "statement_type": "BS",
                "account_id": "ifrs-full_CurrentAssets",
                "account_name": "유동자산",
                "current_amount": 900,
                "previous_amount": 850,
            },
            {
                **base,
                "statement_type": "BS",
                "account_id": "ifrs-full_CurrentLiabilities",
                "account_name": "유동부채",
                "current_amount": 450,
                "previous_amount": 425,
            },
            {
                **base,
                "statement_type": "BS",
                "account_id": "ifrs-full_Equity",
                "account_name": "자본총계",
                "current_amount": 1200,
                "previous_amount": 1100,
            },
            {
                **base,
                "statement_type": "BS",
                "account_id": "ifrs-full_CashAndCashEquivalents",
                "account_name": "현금및현금성자산",
                "current_amount": 300,
                "previous_amount": 250,
            },
            {
                **base,
                "statement_type": "IS",
                "account_id": "ifrs-full_DepreciationAndAmortizationExpense",
                "account_name": "감가상각비및무형자산상각비",
                "current_amount": 20,
                "previous_amount": 18,
            },
            {
                **base,
                "statement_type": "CF",
                "account_id": "ifrs-full_CashFlowsFromUsedInOperatingActivities",
                "account_name": "영업활동현금흐름",
                "current_amount": 150,
                "previous_amount": 120,
            },
            {
                **base,
                "statement_type": "CF",
                "account_id": "dart_PurchaseOfPropertyPlantAndEquipment",
                "account_name": "유형자산의 취득",
                "current_amount": 40,
                "previous_amount": 35,
            },
            {
                **base,
                "statement_type": "CF",
                "account_id": "ifrs-full_DividendsPaidClassifiedAsFinancingActivities",
                "account_name": "배당금의 지급",
                "current_amount": -30,
                "previous_amount": -20,
            },
        ]

    monkeypatch.setattr(main_module, "fetch_open_dart_financial_statements", fake_fetch_open_dart_financial_statements)

    with session_factory() as session:
        market = Market(code="KR", name="Korea", country="KR", currency="KRW", timezone="Asia/Seoul")
        session.add(market)
        session.flush()
        instrument = Instrument(
            market_id=market.id,
            symbol="005930",
            name="삼성전자",
            exchange="KOSPI",
            asset_type="stock",
            is_active=True,
        )
        session.add(instrument)
        session.flush()
        session.add(
            QuoteSnapshot(
                instrument_id=instrument.id,
                snapshot_date=date(2026, 6, 21),
                provider=main_module.KIS_QUOTE_SNAPSHOT_PROVIDER,
                market_cap=10000,
                price=70000,
                change_pct=0,
                volume=1000000,
                trading_value=70000000000,
            )
        )
        session.commit()

    response = client.post(
        "/api/data/opendart/financial-statements/import"
        "?symbol=005930&business_year=2025&report_code=11011&fs_div=CFS"
    )
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == main_module.OPEN_DART_FUNDAMENTAL_PROVIDER
    assert data["saved_count"] == 1
    assert data["summary"]["debt_ratio"] == 66.67
    assert data["summary"]["current_ratio"] == 200.0
    assert data["summary"]["operating_margin"] == 15.0
    assert data["summary"]["free_cash_flow"] == 110
    assert data["summary"]["dividends_paid"] == 30
    assert data["summary"]["ebitda"] == 200
    assert data["summary"]["dividend_growth"] == 50.0

    with session_factory() as session:
        ratio = session.scalar(
            select(FundamentalRatio).where(FundamentalRatio.provider == main_module.OPEN_DART_FUNDAMENTAL_PROVIDER)
        )

    assert ratio is not None
    assert ratio.fiscal_period == "202512"
    assert float(ratio.roe) == 7.5
    assert float(ratio.roa) == 4.5
    assert float(ratio.operating_margin) == 15.0
    assert float(ratio.current_ratio) == 200.0
    assert float(ratio.free_cash_flow) == 110
    assert float(ratio.fcf_yield) == 1.1
    assert float(ratio.dividends_paid) == 30
    assert float(ratio.dividend_yield) == 0.3
    assert float(ratio.payout_ratio) == pytest.approx(33.3333, abs=0.0001)
    assert float(ratio.ev_ebitda) == 52.5


def test_open_dart_fundamental_summary_drops_outlier_derived_ratios(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)

    with session_factory() as session:
        market = Market(code="KR", name="Korea", country="KR", currency="KRW", timezone="Asia/Seoul")
        session.add(market)
        session.flush()
        instrument = Instrument(
            market_id=market.id,
            symbol="000440",
            name="중앙에너비스",
            exchange="KOSDAQ",
            asset_type="stock",
            is_active=True,
        )
        session.add(instrument)
        session.flush()
        session.add(
            QuoteSnapshot(
                instrument_id=instrument.id,
                snapshot_date=date(2026, 7, 11),
                provider=main_module.KIS_QUOTE_SNAPSHOT_PROVIDER,
                market_cap=100,
                price=100,
                change_pct=0,
                volume=1,
                trading_value=100,
            )
        )
        session.commit()

    with session_factory() as session:
        saved_count = main_module._save_open_dart_fundamental_summary(
            session=session,
            symbol="000440",
            name="중앙에너비스",
            exchange="KOSDAQ",
            business_year=2025,
            summary={
                "revenue_growth": -0.44,
                "operating_income_growth": 0.13,
                "net_income_growth": -18.21,
                "roe": -2.14,
                "roa": -2.03,
                "operating_margin": -3.52,
                "net_margin": -2.25,
                "free_cash_flow": 484192640,
                "dividends_paid": 1418827200,
                "current_assets": 9354242983,
                "current_liabilities": 1167171691,
                "current_ratio": 801.45,
                "cash_and_cash_equivalents": 18119373,
                "ebitda": -1743958445,
                "debt_ratio": 5.74,
            },
        )
        ratio = session.scalar(
            select(FundamentalRatio).where(FundamentalRatio.provider == main_module.OPEN_DART_FUNDAMENTAL_PROVIDER)
        )

    assert saved_count == 1
    assert ratio is not None
    assert ratio.fcf_yield is None
    assert ratio.dividend_yield is None
    assert ratio.dividend_stability_score is None
    assert float(ratio.current_ratio) == 801.45


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


def test_krx_instruments_import_saves_to_database(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)

    def fake_fetch_krx_instruments(
        market: str,
        limit: int,
        base_date: str | None = None,
    ) -> list[dict[str, str]]:
        assert market == "KOSPI"
        assert limit == 100
        assert base_date == "20260619"
        return [
            {
                "symbol": "005930",
                "name": "삼성전자",
                "exchange": "KOSPI",
                "asset_type": "stock",
            },
            {
                "symbol": "000660",
                "name": "SK하이닉스",
                "exchange": "KOSPI",
                "asset_type": "stock",
            },
        ]

    monkeypatch.setattr(main_module, "fetch_krx_instruments", fake_fetch_krx_instruments)

    response = client.post(
        "/api/data/krx/instruments/import",
        json={"market": "KOSPI", "limit": 100, "base_date": "20260619"},
    )
    data = response.json()

    assert response.status_code == 201
    assert data["provider"] == "KRX Open API"
    assert data["base_date"] == "20260619"
    assert data["fetched_count"] == 2
    assert data["created_count"] == 2
    assert data["instrument_count"] == 2

    with session_factory() as session:
        samsung = session.scalar(select(Instrument).where(Instrument.symbol == "005930"))

    assert samsung is not None
    assert samsung.name == "삼성전자"
    assert samsung.exchange == "KOSPI"


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


def test_kis_websocket_approval_status_does_not_expose_key(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "get_kis_ws_approval_status",
        lambda: {
            "provider": "KIS Open API",
            "ready": True,
            "environment": "paper",
            "base_url": "https://openapivts.koreainvestment.com:29443",
            "ws_url": "ws://ops.koreainvestment.com:31000",
            "approval_key_cached": True,
            "expires_in_seconds": 3600,
        },
    )

    response = client.get("/api/data/kis/websocket/approval/status")
    data = response.json()

    assert response.status_code == 200
    assert data["ready"] is True
    assert data["environment"] == "paper"
    assert data["approval_key_cached"] is True
    assert "approval_key" not in data


def test_kis_websocket_approval_issue_uses_force_refresh(monkeypatch) -> None:
    force_refresh_values: list[bool] = []

    def fake_get_kis_ws_approval_key(*, force_refresh: bool = False) -> str:
        force_refresh_values.append(force_refresh)
        return "approval-key"

    monkeypatch.setattr(main_module, "get_kis_ws_approval_key", fake_get_kis_ws_approval_key)
    monkeypatch.setattr(
        main_module,
        "get_kis_ws_approval_status",
        lambda: {
            "provider": "KIS Open API",
            "ready": True,
            "environment": "paper",
            "base_url": "https://openapivts.koreainvestment.com:29443",
            "ws_url": "ws://ops.koreainvestment.com:31000",
            "approval_key_cached": True,
            "expires_in_seconds": 3600,
        },
    )

    response = client.post(
        "/api/data/kis/websocket/approval-key",
        json={"force_refresh": True},
    )
    data = response.json()

    assert response.status_code == 200
    assert force_refresh_values == [True]
    assert data["approval_key_cached"] is True
    assert "approval_key" not in data


def test_parse_kis_realtime_quote_message(monkeypatch) -> None:
    monkeypatch.setattr("quantmate_api.kis_realtime.today_kst", lambda: date(2026, 6, 21))
    message = (
        "0|H0STCNT0|001|"
        "005930^093015^71000^2^1200^1.72^70500^70000^72000^69500^71100^71000^35^123456^876543210"
    )

    quote = parse_kis_realtime_quote(message)

    assert quote is not None
    assert quote.symbol == "005930"
    assert quote.trade_time == "2026-06-21T09:30:15"
    assert quote.price == 71000
    assert quote.change == 1200
    assert quote.change_rate == 1.72
    assert quote.ask_price == 71100
    assert quote.bid_price == 71000
    assert quote.trade_volume == 35
    assert quote.accumulated_volume == 123456
    assert quote.accumulated_trading_value == 876543210


def test_kis_realtime_quote_endpoints_use_service(monkeypatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    class FakeRealtimeService:
        async def status(self) -> KisRealtimeStatus:
            return KisRealtimeStatus(
                provider="KIS Open API",
                environment="paper",
                ws_url="ws://ops.koreainvestment.com:31000",
                running=True,
                connected=False,
                subscribed_symbols=["005930"],
                quote_count=0,
                last_message_at=None,
                last_error="",
            )

        async def latest_quotes(self) -> list[object]:
            return []

        async def subscribe(self, symbols: list[str]) -> KisRealtimeStatus:
            calls.append(("subscribe", symbols))
            return await self.status()

        async def unsubscribe(self, symbols: list[str]) -> KisRealtimeStatus:
            calls.append(("unsubscribe", symbols))
            return await self.status()

        async def stop(self) -> KisRealtimeStatus:
            calls.append(("stop", []))
            return KisRealtimeStatus(
                provider="KIS Open API",
                environment="paper",
                ws_url="ws://ops.koreainvestment.com:31000",
                running=False,
                connected=False,
                subscribed_symbols=[],
                quote_count=0,
                last_message_at=None,
                last_error="",
            )

    monkeypatch.setattr(main_module, "kis_realtime_quote_service", FakeRealtimeService())

    status_response = client.get("/api/data/kis/realtime/quotes/status")
    subscribe_response = client.post(
        "/api/data/kis/realtime/quotes/subscribe",
        json={"symbols": ["005930", "000660"]},
    )
    latest_response = client.get("/api/data/kis/realtime/quotes/latest")
    unsubscribe_response = client.post(
        "/api/data/kis/realtime/quotes/unsubscribe",
        json={"symbols": ["000660"]},
    )
    stop_response = client.post("/api/data/kis/realtime/quotes/stop")

    assert status_response.status_code == 200
    assert status_response.json()["running"] is True
    assert subscribe_response.status_code == 200
    assert latest_response.status_code == 200
    assert latest_response.json() == []
    assert unsubscribe_response.status_code == 200
    assert stop_response.status_code == 200
    assert stop_response.json()["running"] is False
    assert calls == [
        ("subscribe", ["005930", "000660"]),
        ("unsubscribe", ["000660"]),
        ("stop", []),
    ]


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


def test_kis_instruments_import_saves_market_cap_ranking(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)

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
        session.add(
            Instrument(
                market_id=market.id,
                symbol="005930",
                name="삼성전자-old",
                exchange="KOSPI",
                asset_type="stock",
                is_active=False,
            )
        )
        session.commit()

    def fake_fetch_kis_market_cap_ranking(limit: int = 50, market: str = "ALL") -> list[dict[str, object]]:
        assert limit == 3
        assert market == "ALL"
        return [
            {
                "provider": "KIS Open API",
                "symbol": "005930",
                "name": "삼성전자",
                "exchange": "KOSPI",
            },
            {
                "provider": "KIS Open API",
                "symbol": "000660",
                "name": "SK하이닉스",
                "exchange": "KOSPI",
            },
            {
                "provider": "KIS Open API",
                "symbol": "",
                "name": "",
                "exchange": "KOSDAQ",
            },
        ]

    monkeypatch.setattr(main_module, "fetch_kis_market_cap_ranking", fake_fetch_kis_market_cap_ranking)

    response = client.post("/api/data/kis/instruments/import", json={"market": "ALL", "limit": 3})
    data = response.json()

    assert response.status_code == 201
    assert data["provider"] == "KIS Open API"
    assert data["fetched_count"] == 3
    assert data["created_count"] == 1
    assert data["updated_count"] == 1
    assert data["skipped_count"] == 1
    assert data["instrument_count"] == 2

    with session_factory() as session:
        samsung = session.scalar(select(Instrument).where(Instrument.symbol == "005930"))
        hynix = session.scalar(select(Instrument).where(Instrument.symbol == "000660"))
        job = session.scalar(select(DataImportJob))

    assert samsung is not None
    assert samsung.name == "삼성전자"
    assert samsung.is_active is True
    assert hynix is not None
    assert hynix.exchange == "KOSPI"
    assert job is not None
    assert job.provider == "KIS Open API"
    assert job.job_type == "instruments"
    assert job.status == "completed"


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


def test_local_instruments_returns_db_symbols(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    with session_factory() as session:
        market = Market(code="KR", name="한국 주식", country="KR", currency="KRW", timezone="Asia/Seoul")
        session.add(market)
        session.flush()
        session.add_all(
            [
                Instrument(
                    market_id=market.id,
                    symbol="005930",
                    name="삼성전자",
                    exchange="KOSPI",
                    asset_type="stock",
                    is_active=True,
                ),
                Instrument(
                    market_id=market.id,
                    symbol="247540",
                    name="에코프로비엠",
                    exchange="KOSDAQ",
                    asset_type="stock",
                    is_active=True,
                ),
            ]
        )
        session.commit()

    response = client.get("/api/data/instruments/local?market=KOSPI&limit=10")
    data = response.json()

    assert response.status_code == 200
    assert data["market"] == "KOSPI"
    assert data["total"] == 1
    assert data["items"][0]["symbol"] == "005930"
    assert data["items"][0]["name"] == "삼성전자"


def test_enrichment_import_saves_kis_auxiliary_data(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    monkeypatch.setattr(main_module, "is_kis_open_api_ready", lambda: True)
    monkeypatch.setattr(main_module, "is_open_dart_ready", lambda: False)

    def fake_fetch_kis_current_price(symbol: str) -> dict[str, object]:
        assert symbol == "005930"
        return {
            "provider": "KIS Open API",
            "symbol": "005930",
            "name": "삼성전자",
            "price": 78000,
            "change": 1000,
            "change_rate": 1.2,
            "volume": 1000000,
            "trading_value": 78000000000,
            "open": 77000,
            "high": 79000,
            "low": 76000,
            "market_state": "정규장",
            "market_cap": 465000000000000,
            "per": 12.5,
            "pbr": 1.1,
        }

    def fake_fetch_kis_financial_ratios(
        symbol: str,
        period_type: str = "annual",
        limit: int = 8,
    ) -> list[dict[str, object]]:
        assert symbol == "005930"
        assert period_type == "annual"
        assert limit == 8
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
                "debt_ratio": 42.1,
            }
        ]

    def fake_fetch_kis_investor_trade_daily(
        symbol: str,
        base_date: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, object]]:
        assert symbol == "005930"
        assert base_date == date(2026, 6, 30)
        return [
            {
                "provider": "KIS Open API",
                "symbol": "005930",
                "trade_date": "2026-06-28",
                "foreign_net_buy_qty": 1000,
                "institution_net_buy_qty": 500,
                "pension_net_buy_qty": 100,
                "foreign_net_buy_value": 1000000000,
                "institution_net_buy_value": 500000000,
                "pension_net_buy_value": 100000000,
                "individual_net_buy_value": -1600000000,
            },
            {
                "provider": "KIS Open API",
                "symbol": "005930",
                "trade_date": "2026-05-31",
                "foreign_net_buy_qty": 999,
            },
        ]

    def fake_fetch_kis_daily_short_sale(
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, object]]:
        assert symbol == "005930"
        assert start == date(2026, 6, 1)
        assert end == date(2026, 6, 30)
        return [
            {
                "provider": "KIS Open API",
                "symbol": "005930",
                "trade_date": "2026-06-28",
                "short_sale_volume": 1000,
                "short_sale_volume_ratio": 3.2,
                "short_sale_value": 800000000,
                "short_sale_value_ratio": 2.8,
            }
        ]

    def fake_fetch_kis_daily_credit_balance(
        symbol: str,
        base_date: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, object]]:
        assert symbol == "005930"
        assert base_date == date(2026, 6, 30)
        return [
            {
                "provider": "KIS Open API",
                "symbol": "005930",
                "trade_date": "2026-06-28",
                "margin_loan_balance": 100000000000,
                "margin_loan_balance_rate": 1.2,
                "margin_loan_new_amount": 12000000000,
                "margin_loan_redeem_amount": 8000000000,
                "stock_loan_balance": 1000000000,
                "stock_loan_balance_rate": 0.1,
            }
        ]

    monkeypatch.setattr(main_module, "fetch_kis_current_price", fake_fetch_kis_current_price)
    monkeypatch.setattr(main_module, "fetch_kis_financial_ratios", fake_fetch_kis_financial_ratios)
    monkeypatch.setattr(main_module, "fetch_kis_investor_trade_daily", fake_fetch_kis_investor_trade_daily)
    monkeypatch.setattr(main_module, "fetch_kis_daily_short_sale", fake_fetch_kis_daily_short_sale)
    monkeypatch.setattr(main_module, "fetch_kis_daily_credit_balance", fake_fetch_kis_daily_credit_balance)

    response = client.post(
        "/api/data/enrichment/import",
        json={
            "symbol": "005930",
            "name": "삼성전자",
            "exchange": "KOSPI",
            "start": "2026-06-01",
            "end": "2026-06-30",
            "include_open_dart": False,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["quote_saved"] is True
    assert data["kis_fundamental_saved_count"] == 1
    assert data["supply_flow_saved_count"] == 1
    assert data["risk_indicator_saved_count"] == 1

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(QuoteSnapshot)) == 1
        assert session.scalar(select(func.count()).select_from(FundamentalRatio)) == 1
        assert session.scalar(select(func.count()).select_from(SupplyFlowDaily)) == 1
        assert session.scalar(select(func.count()).select_from(RiskIndicatorDaily)) == 1


def test_enrichment_coverage_reports_complete_auxiliary_data(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    with session_factory() as session:
        market = Market(code="KR", name="한국 주식", country="KR", currency="KRW", timezone="Asia/Seoul")
        session.add(market)
        session.flush()
        instrument = Instrument(
            market_id=market.id,
            symbol="005930",
            name="삼성전자",
            exchange="KOSPI",
            asset_type="stock",
            is_active=True,
        )
        session.add(instrument)
        session.flush()
        session.add(
            QuoteSnapshot(
                instrument_id=instrument.id,
                snapshot_date=main_module.today_kst(),
                provider=main_module.KIS_QUOTE_SNAPSHOT_PROVIDER,
                price=78000,
                change_pct=1.2,
                volume=1000000,
                trading_value=78000000000,
                market_cap=465000000000000,
                per=12.5,
                pbr=1.1,
                eps=None,
                bps=None,
                turnover_pct=None,
                foreign_holding_rate=None,
                foreign_net_buy_qty=None,
                program_net_buy_qty=None,
                high_52w=None,
                low_52w=None,
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
            )
        )
        session.add(
            FundamentalRatio(
                instrument_id=instrument.id,
                fiscal_period="202512",
                period_type="annual",
                provider=main_module.OPEN_DART_FUNDAMENTAL_PROVIDER,
                revenue_growth=20.0,
            )
        )
        for offset in range(5):
            trade_date = date(2026, 6, 1) + timedelta(days=offset)
            session.add(
                SupplyFlowDaily(
                    instrument_id=instrument.id,
                    trade_date=trade_date,
                    provider=main_module.KIS_SUPPLY_FLOW_PROVIDER,
                    foreign_net_buy_qty=1000,
                    institution_net_buy_qty=500,
                    pension_net_buy_qty=100,
                    foreign_net_buy_value=1000000000,
                    institution_net_buy_value=500000000,
                    pension_net_buy_value=100000000,
                    individual_net_buy_value=-1600000000,
                )
            )
            session.add(
                RiskIndicatorDaily(
                    instrument_id=instrument.id,
                    trade_date=trade_date,
                    provider=main_module.KIS_RISK_INDICATOR_PROVIDER,
                    short_sale_volume=1000,
                    short_sale_volume_ratio=3.2,
                    short_sale_value=800000000,
                    short_sale_value_ratio=2.8,
                    margin_loan_balance=100000000000,
                    margin_loan_balance_rate=1.2,
                    margin_loan_new_amount=12000000000,
                    margin_loan_redeem_amount=8000000000,
                    stock_loan_balance=1000000000,
                    stock_loan_balance_rate=0.1,
                )
            )
        session.commit()

    response = client.post(
        "/api/data/enrichment/coverage",
        json={
            "symbol": "005930",
            "name": "삼성전자",
            "exchange": "KOSPI",
            "start": "2026-06-01",
            "end": "2026-06-05",
            "open_dart_business_years": [2025],
            "min_ratio": 0.8,
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["complete"] is True
    assert data["static_complete"] is True
    assert data["monthly_complete"] is True
    assert data["quote_exists"] is True
    assert data["kis_fundamental_count"] == 1
    assert data["open_dart_stored_years"] == [2025]
    assert data["supply_flow_coverage_ratio"] == 1.0
    assert data["risk_indicator_coverage_ratio"] == 1.0
    assert data["missing_parts"] == []


def test_enrichment_coverage_reports_missing_auxiliary_data(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    with session_factory() as session:
        market = Market(code="KR", name="한국 주식", country="KR", currency="KRW", timezone="Asia/Seoul")
        session.add(market)
        session.flush()
        session.add(
            Instrument(
                market_id=market.id,
                symbol="005930",
                name="삼성전자",
                exchange="KOSPI",
                asset_type="stock",
                is_active=True,
            )
        )
        session.commit()

    response = client.post(
        "/api/data/enrichment/coverage",
        json={
            "symbol": "005930",
            "name": "삼성전자",
            "exchange": "KOSPI",
            "start": "2026-06-01",
            "end": "2026-06-05",
            "open_dart_business_years": [2025],
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["complete"] is False
    assert "KIS 현재가" in data["missing_parts"]
    assert "KIS 재무비율" in data["missing_parts"]
    assert "OpenDART 재무요약" in data["missing_parts"]
    assert "KIS 수급" in data["missing_parts"]
    assert "KIS 리스크" in data["missing_parts"]


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


def test_kis_ws_approval_key_reuses_file_cache(monkeypatch, tmp_path) -> None:
    approval_path = tmp_path / "kis_ws_approval_cache.json"
    issue_count = 0

    monkeypatch.setenv("KIS_APP_KEY", "app-key")
    monkeypatch.setenv("KIS_APP_SECRET", "app-secret")
    monkeypatch.setenv("KIS_BASE_URL", "https://openapivts.koreainvestment.com:29443")
    monkeypatch.setenv("KIS_WS_URL", "ws://ops.koreainvestment.com:31000")
    monkeypatch.delenv("KIS_WS_APPROVAL_KEY", raising=False)
    monkeypatch.setenv("KIS_WS_APPROVAL_CACHE_PATH", str(approval_path))
    market_data_module.KIS_WS_APPROVAL_CACHE.clear()

    def fake_issue_kis_ws_approval_key(
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
            "approval_key": "cached-approval-key",
            "expires_in": 3600,
        }

    monkeypatch.setattr(market_data_module, "issue_kis_ws_approval_key", fake_issue_kis_ws_approval_key)

    assert market_data_module.get_kis_ws_approval_key() == "cached-approval-key"
    market_data_module.KIS_WS_APPROVAL_CACHE.clear()
    assert market_data_module.get_kis_ws_approval_key() == "cached-approval-key"
    status = market_data_module.get_kis_ws_approval_status()

    assert issue_count == 1
    assert approval_path.exists()
    assert status["approval_key_cached"] is True
    assert "approval_key" not in status


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


def test_krx_daily_prices_preview_uses_market_data_provider(monkeypatch) -> None:
    def fake_fetch_krx_daily_prices(
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
                "symbol": symbol,
                "trade_date": "2026-06-03",
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
                "symbol": symbol,
                "trade_date": "2026-06-04",
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

    monkeypatch.setattr(main_module, "fetch_krx_daily_prices", fake_fetch_krx_daily_prices)

    response = client.get(
        "/api/data/krx/daily-prices"
        "?symbol=005930&exchange=KOSPI&start=2026-06-01&end=2026-06-05&limit=1"
    )
    data = response.json()

    assert response.status_code == 200
    assert data["provider"] == "KRX Open API"
    assert data["symbol"] == "005930"
    assert data["exchange"] == "KOSPI"
    assert data["count"] == 1
    assert data["prices"][0]["trade_date"] == "2026-06-04"


def test_krx_daily_prices_import_saves_daily_prices(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)

    def fake_fetch_krx_daily_prices(
        symbol: str,
        exchange: str,
        start: date | None = None,
        end: date | None = None,
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
                "provider": "KRX Open API",
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
                "provider": "KRX Open API",
            },
        ]

    monkeypatch.setattr(main_module, "fetch_krx_daily_prices", fake_fetch_krx_daily_prices)

    response = client.post(
        "/api/data/krx/daily-prices/import",
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
    assert data["provider"] == "KRX Open API"
    assert data["saved_count"] == 2

    with session_factory() as session:
        saved_count = session.scalar(select(func.count()).select_from(DailyPrice))
        provider_count = session.scalar(
            select(func.count()).select_from(DailyPrice).where(DailyPrice.provider == "KRX Open API")
        )
        assert saved_count == 2
        assert provider_count == 2


def test_krx_market_daily_prices_import_saves_market_rows(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)

    def fake_fetch_krx_market_daily_prices(
        market: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        assert market == "KOSPI"
        assert start == date(2026, 6, 1)
        assert end == date(2026, 6, 2)
        return [
            {
                "symbol": "005930",
                "name": "삼성전자",
                "exchange": "KOSPI",
                "trade_date": "2026-06-01",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 102.0,
                "adjusted_close": None,
                "volume": 1000,
                "trading_value": 102000,
                "provider": "KRX Open API",
            },
            {
                "symbol": "000660",
                "name": "SK하이닉스",
                "exchange": "KOSPI",
                "trade_date": "2026-06-01",
                "open": 200.0,
                "high": 205.0,
                "low": 198.0,
                "close": 202.0,
                "adjusted_close": None,
                "volume": 2000,
                "trading_value": 404000,
                "provider": "KRX Open API",
            },
        ]

    monkeypatch.setattr(main_module, "fetch_krx_market_daily_prices", fake_fetch_krx_market_daily_prices)

    response = client.post(
        "/api/data/krx/daily-prices/import/market",
        json={"market": "KOSPI", "start": "2026-06-01", "end": "2026-06-02"},
    )
    data = response.json()

    assert response.status_code == 201
    assert data["provider"] == "KRX Open API"
    assert data["market"] == "KOSPI"
    assert data["saved_count"] == 2

    with session_factory() as session:
        saved_count = session.scalar(select(func.count()).select_from(DailyPrice))
        instrument_count = session.scalar(select(func.count()).select_from(Instrument))
        assert saved_count == 2
        assert instrument_count == 2


def test_krx_daily_price_coverage_reports_complete_market_range(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=[
            {"symbol": "005930", "name": "삼성전자", "exchange": "KOSPI"},
            {"symbol": "000660", "name": "SK하이닉스", "exchange": "KOSPI"},
        ],
        provider="KRX Open API",
        start=date(2026, 6, 1),
        days=5,
    )

    response = client.get(
        "/api/data/krx/daily-prices/coverage",
        params={"market": "KOSPI", "start": "2026-06-01", "end": "2026-06-05"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["market"] == "KOSPI"
    assert data["expected_weekdays"] == 5
    assert data["stored_trade_dates"] == 5
    assert data["instrument_count"] == 2
    assert data["complete"] is True


def test_krx_daily_price_coverage_reports_incomplete_market_range(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    seed_daily_prices(
        session_factory,
        symbols=[{"symbol": "005930", "name": "삼성전자", "exchange": "KOSPI"}],
        provider="KRX Open API",
        start=date(2026, 6, 1),
        days=2,
    )

    response = client.get(
        "/api/data/krx/daily-prices/coverage",
        params={"market": "KOSPI", "start": "2026-06-01", "end": "2026-06-05"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["expected_weekdays"] == 5
    assert data["stored_trade_dates"] == 2
    assert data["coverage_ratio"] == 0.4
    assert data["complete"] is False


def test_manual_data_refresh_job_imports_krx_market_data(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)
    main_module.MANUAL_DATA_REFRESH_JOBS.clear()
    monkeypatch.setattr(main_module, "default_krx_base_date", lambda: "20260622")
    monkeypatch.setattr(main_module, "_expected_latest_daily_price_date", lambda: date(2026, 6, 22))

    def fake_fetch_krx_instruments(
        market: str,
        limit: int = 3000,
        base_date: str | None = None,
    ) -> list[dict[str, object]]:
        assert market == "ALL"
        assert base_date == "20260622"
        return [
            {"symbol": "005930", "name": "삼성전자", "exchange": "KOSPI", "asset_type": "stock"},
            {"symbol": "091990", "name": "셀트리온헬스케어", "exchange": "KOSDAQ", "asset_type": "stock"},
        ]

    def fake_fetch_krx_market_daily_prices(
        market: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        assert start == date(2026, 6, 19)
        assert end == date(2026, 6, 22)
        symbol = "005930" if market == "KOSPI" else "091990"
        name = "삼성전자" if market == "KOSPI" else "셀트리온헬스케어"
        return [
            {
                "symbol": symbol,
                "name": name,
                "exchange": market,
                "trade_date": "2026-06-22",
                "open": 100.0,
                "high": 110.0,
                "low": 95.0,
                "close": 105.0,
                "volume": 1000,
                "trading_value": 105000,
                "provider": "KRX Open API",
            }
        ]

    monkeypatch.setattr(main_module, "fetch_krx_instruments", fake_fetch_krx_instruments)
    monkeypatch.setattr(main_module, "fetch_krx_market_daily_prices", fake_fetch_krx_market_daily_prices)

    response = client.post(
        "/api/data/manual-refresh",
        json={"refresh_instruments": True, "refresh_daily_prices": True, "markets": ["KOSPI", "KOSDAQ"], "lookback_days": 3},
    )
    data = response.json()

    assert response.status_code == 202
    assert data["status"] in {"queued", "running"}

    job_data = data
    for _ in range(30):
        status_response = client.get(f"/api/data/manual-refresh/{data['job_id']}")
        job_data = status_response.json()
        if job_data["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert job_data["status"] == "completed"
    assert job_data["progress_pct"] == 100
    assert job_data["saved_count"] == 2
    assert job_data["latest_daily_price_date"] == "2026-06-22"

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Instrument)) == 2
        assert session.scalar(select(func.count()).select_from(DailyPrice)) == 2


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


def test_yahoo_daily_price_import_normalizes_ohlcv_range(monkeypatch) -> None:
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
                "close": 108.0,
                "adjusted_close": 108.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            }
        ]

    monkeypatch.setattr(main_module, "fetch_yahoo_daily_prices", fake_fetch_yahoo_daily_prices)

    response = client.post(
        "/api/data/yahoo/daily-prices/import",
        json={
            "symbol": "005930",
            "name": "삼성전자",
            "exchange": "KOSPI",
            "start": "2026-06-01",
            "end": "2026-06-01",
        },
    )

    assert response.status_code == 201

    with session_factory() as session:
        row = session.scalar(select(DailyPrice))
        assert row is not None
        assert row.high_price == row.close_price
        assert row.low_price <= row.open_price <= row.high_price


def test_yahoo_daily_price_import_saves_us_market_for_us_exchange(monkeypatch) -> None:
    session_factory = use_sqlite_session(monkeypatch)

    def fake_fetch_yahoo_daily_prices(
        symbol: str,
        exchange: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, object]]:
        assert symbol == "AAPL"
        assert exchange == "NASDAQ"
        return [
            {
                "symbol": "AAPL",
                "trade_date": "2026-06-01",
                "open": 200.0,
                "high": 205.0,
                "low": 198.0,
                "close": 203.0,
                "adjusted_close": 203.0,
                "volume": 1000,
                "provider": "Yahoo Finance",
            }
        ]

    monkeypatch.setattr(main_module, "fetch_yahoo_daily_prices", fake_fetch_yahoo_daily_prices)

    response = client.post(
        "/api/data/yahoo/daily-prices/import",
        json={
            "symbol": "AAPL",
            "name": "Apple",
            "exchange": "NASDAQ",
            "start": "2026-06-01",
            "end": "2026-06-01",
        },
    )

    assert response.status_code == 201

    with session_factory() as session:
        instrument = session.scalar(select(Instrument).where(Instrument.symbol == "AAPL"))
        assert instrument is not None
        assert instrument.exchange == "NASDAQ"
        assert instrument.market.code == "US"
        assert instrument.market.currency == "USD"
        assert instrument.market.timezone == "America/New_York"


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
    assert data["final_amount"] == 1096500
    assert "거래비용 0.25%" in data["notice"]
    assert "슬리피지 0.10%" in data["notice"]
    assert data["equity_curve"] == [
        {"label": "2026.01", "portfolio": 1000000},
        {"label": "2026.02", "portfolio": 1096500},
    ]


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
    assert data["final_amount"] == 1096500
    assert "거래비용 0.25%" in data["notice"]
    assert "슬리피지 0.10%" in data["notice"]


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
    assert data["final_amount"] == 1096500
    assert "거래비용 0.25%" in data["notice"]
    assert "슬리피지 0.10%" in data["notice"]
    assert data["rebalance_history"][0]["holdings"] == "1종목"
    assert "한화에어로스페이스" in data["rebalance_history"][0]["entries"]
    assert "에코프로비엠" not in data["rebalance_history"][0]["entries"]
