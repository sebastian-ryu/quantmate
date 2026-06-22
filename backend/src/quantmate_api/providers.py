from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from quantmate_api.market_data import (
    fetch_kis_daily_credit_balance,
    fetch_kis_daily_prices,
    fetch_kis_daily_short_sale,
    fetch_kis_domestic_balance,
    fetch_kis_financial_ratios,
    fetch_kis_investor_trade_daily,
    fetch_kis_market_cap_ranking,
    fetch_krx_instruments,
    fetch_krx_daily_prices,
    fetch_open_dart_financial_statements,
    fetch_yahoo_daily_prices,
    get_kis_ws_approval_status,
    get_open_dart_corp_code_cache_status,
    has_kis_account_credentials,
    is_kis_open_api_ready,
    is_krx_open_api_ready,
    is_open_dart_ready,
    summarize_open_dart_financial_statements,
)
from quantmate_api.time_utils import today_kst


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    scope: str
    status: str
    ready: bool

    def as_response_row(self) -> dict[str, str | bool]:
        return {
            "name": self.name,
            "scope": self.scope,
            "status": self.status,
            "ready": self.ready,
        }


class MarketDataProvider(Protocol):
    name: str
    scope: str

    def status(self) -> ProviderStatus:
        pass


class InstrumentProvider(MarketDataProvider, Protocol):
    def fetch_instruments(
        self,
        *,
        market: str = "ALL",
        limit: int = 200,
        base_date: str | None = None,
    ) -> list[dict[str, Any]]:
        pass


class DailyPriceProvider(MarketDataProvider, Protocol):
    def fetch_daily_prices(
        self,
        *,
        symbol: str,
        exchange: str = "KOSPI",
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, Any]]:
        pass


class FundamentalProvider(MarketDataProvider, Protocol):
    def fetch_financial_ratios(
        self,
        *,
        symbol: str,
        period_type: str = "annual",
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        pass


class SupplyFlowProvider(MarketDataProvider, Protocol):
    def fetch_investor_trade_daily(
        self,
        *,
        symbol: str,
        base_date: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        pass


class RiskIndicatorProvider(MarketDataProvider, Protocol):
    def fetch_daily_short_sale(
        self,
        *,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        pass

    def fetch_daily_credit_balance(
        self,
        *,
        symbol: str,
        base_date: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        pass


class BrokerProvider(MarketDataProvider, Protocol):
    def fetch_balance(self) -> dict[str, Any]:
        pass


@dataclass(frozen=True)
class YahooFinanceProvider:
    name: str = "Yahoo Finance"
    scope: str = "KR/US 일봉 임시 백테스트 데이터"

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            scope=self.scope,
            status="임시 사용 가능",
            ready=True,
        )

    def fetch_daily_prices(
        self,
        *,
        symbol: str,
        exchange: str = "KOSPI",
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, Any]]:
        return fetch_yahoo_daily_prices(symbol=symbol, exchange=exchange, start=start, end=end)


@dataclass(frozen=True)
class KrxOpenApiProvider:
    name: str = "KRX Open API"
    scope: str = "공식 인증키 기반 종목/OHLCV"

    def status(self) -> ProviderStatus:
        ready = is_krx_open_api_ready()
        return ProviderStatus(
            name=self.name,
            scope=self.scope,
            status="인증키 설정됨" if ready else "API 인증키 필요",
            ready=ready,
        )

    def fetch_instruments(
        self,
        *,
        market: str = "ALL",
        limit: int = 200,
        base_date: str | None = None,
    ) -> list[dict[str, Any]]:
        return fetch_krx_instruments(market=market, limit=limit, base_date=base_date)

    def fetch_daily_prices(
        self,
        *,
        symbol: str,
        exchange: str = "KOSPI",
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, Any]]:
        return fetch_krx_daily_prices(symbol=symbol, exchange=exchange, start=start, end=end)


@dataclass(frozen=True)
class KisOpenApiProvider:
    name: str = "KIS Open API"
    scope: str = "현재가/일봉/재무/수급/리스크/계좌"

    def status(self) -> ProviderStatus:
        ready = is_kis_open_api_ready()
        return ProviderStatus(
            name=self.name,
            scope=self.scope,
            status="인증정보 설정됨" if ready else "App Key/Secret 필요",
            ready=ready,
        )

    def fetch_instruments(
        self,
        *,
        market: str = "ALL",
        limit: int = 200,
        base_date: str | None = None,
    ) -> list[dict[str, Any]]:
        del base_date
        return fetch_kis_market_cap_ranking(limit=limit, market=market)

    def fetch_daily_prices(
        self,
        *,
        symbol: str,
        exchange: str = "KOSPI",
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, Any]]:
        del exchange
        return fetch_kis_daily_prices(symbol=symbol, start=start, end=end)

    def fetch_financial_ratios(
        self,
        *,
        symbol: str,
        period_type: str = "annual",
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        return fetch_kis_financial_ratios(symbol=symbol, period_type=period_type, limit=limit)

    def fetch_investor_trade_daily(
        self,
        *,
        symbol: str,
        base_date: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        return fetch_kis_investor_trade_daily(symbol=symbol, base_date=base_date, limit=limit)

    def fetch_daily_short_sale(
        self,
        *,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        return fetch_kis_daily_short_sale(symbol=symbol, start=start, end=end, limit=limit)

    def fetch_daily_credit_balance(
        self,
        *,
        symbol: str,
        base_date: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        return fetch_kis_daily_credit_balance(symbol=symbol, base_date=base_date, limit=limit)


@dataclass(frozen=True)
class KisBrokerProvider:
    name: str = "KIS 계좌"
    scope: str = "모의투자/실계좌 잔고와 주문 준비 상태"

    def status(self) -> ProviderStatus:
        ready = has_kis_account_credentials()
        return ProviderStatus(
            name=self.name,
            scope=self.scope,
            status="계좌 설정됨" if ready else "계좌번호 설정 필요",
            ready=ready,
        )

    def fetch_balance(self) -> dict[str, Any]:
        return fetch_kis_domestic_balance()


@dataclass(frozen=True)
class KisRealtimeProvider:
    name: str = "KIS WebSocket"
    scope: str = "실시간 시세"

    def status(self) -> ProviderStatus:
        status = get_kis_ws_approval_status()
        cached = bool(status.get("approval_key_cached"))
        has_credentials = is_kis_open_api_ready()

        if cached:
            message = "접속키 캐시됨"
        elif has_credentials:
            message = "App Key/Secret으로 접속키 발급 가능"
        else:
            message = "App Key/Secret 필요"

        return ProviderStatus(
            name=self.name,
            scope=self.scope,
            status=message,
            ready=cached or has_credentials,
        )


@dataclass(frozen=True)
class OpenDartProvider:
    name: str = "OpenDART"
    scope: str = "재무제표/공시"

    def status(self) -> ProviderStatus:
        ready = is_open_dart_ready()
        cache_status = get_open_dart_corp_code_cache_status()
        cached_count = int(cache_status.get("cached_count") or 0)
        if ready and cached_count > 0:
            status = f"API 키 설정됨, 고유번호 {cached_count:,}건 캐시"
        elif ready:
            status = "API 키 설정됨"
        else:
            status = "API 키 필요"

        return ProviderStatus(
            name=self.name,
            scope=self.scope,
            status=status,
            ready=ready,
        )

    def fetch_financial_ratios(
        self,
        *,
        symbol: str,
        period_type: str = "annual",
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        normalized_period_type = period_type.strip().lower()
        if normalized_period_type not in {"annual", "year", "yearly"}:
            return []

        latest_year = today_kst().year - 1
        earliest_year = max(2015, latest_year - max(1, min(limit, 8)) + 1)
        rows: list[dict[str, Any]] = []
        for business_year in range(latest_year, earliest_year - 1, -1):
            items = fetch_open_dart_financial_statements(
                symbol=symbol,
                business_year=business_year,
                report_code="11011",
                fs_div="CFS",
            )
            if not items:
                continue
            summary = summarize_open_dart_financial_statements(items)
            rows.append(
                {
                    "provider": self.name,
                    "symbol": symbol.strip().upper(),
                    "fiscal_period": f"{business_year}12",
                    "period_type": "annual",
                    **summary,
                }
            )
        return rows


@dataclass(frozen=True)
class ProviderRegistry:
    instrument_providers: tuple[InstrumentProvider, ...]
    daily_price_providers: tuple[DailyPriceProvider, ...]
    fundamental_providers: tuple[FundamentalProvider, ...]
    supply_flow_providers: tuple[SupplyFlowProvider, ...]
    risk_indicator_providers: tuple[RiskIndicatorProvider, ...]
    broker_providers: tuple[BrokerProvider, ...]
    status_providers: tuple[MarketDataProvider, ...]

    def status_rows(self) -> list[dict[str, str | bool]]:
        return [provider.status().as_response_row() for provider in self.status_providers]

    def daily_price_provider_names(self) -> tuple[str, ...]:
        return tuple(provider.name for provider in self.daily_price_providers)


def build_provider_registry() -> ProviderRegistry:
    kis = KisOpenApiProvider()
    krx = KrxOpenApiProvider()
    yahoo = YahooFinanceProvider()
    broker = KisBrokerProvider()
    realtime = KisRealtimeProvider()
    open_dart = OpenDartProvider()

    return ProviderRegistry(
        instrument_providers=(krx, kis),
        daily_price_providers=(krx, kis, yahoo),
        fundamental_providers=(kis, open_dart),
        supply_flow_providers=(kis,),
        risk_indicator_providers=(kis,),
        broker_providers=(broker,),
        status_providers=(kis, broker, realtime, yahoo, krx, open_dart),
    )


def provider_status_rows() -> list[dict[str, str | bool]]:
    return build_provider_registry().status_rows()


def daily_price_provider_names() -> tuple[str, ...]:
    return build_provider_registry().daily_price_provider_names()
