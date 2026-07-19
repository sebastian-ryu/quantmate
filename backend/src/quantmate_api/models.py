from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from quantmate_api.time_utils import now_kst_naive


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst_naive, server_default=func.now())


class Market(TimestampMixin, Base):
    __tablename__ = "markets"
    __table_args__ = (UniqueConstraint("code", name="uq_markets_code"), {"mysql_charset": "utf8mb4"})

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(2))
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(50))

    instruments: Mapped[list[Instrument]] = relationship(back_populates="market")


class Instrument(TimestampMixin, Base):
    __tablename__ = "instruments"
    __table_args__ = (
        Index("ix_instruments_symbol", "symbol"),
        UniqueConstraint("market_id", "symbol", name="uq_instruments_market_symbol"),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    symbol: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    exchange: Mapped[str] = mapped_column(String(40))
    asset_type: Mapped[str] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    market: Mapped[Market] = relationship(back_populates="instruments")
    daily_prices: Mapped[list[DailyPrice]] = relationship(back_populates="instrument")
    quote_snapshots: Mapped[list[QuoteSnapshot]] = relationship(back_populates="instrument")
    supply_flow_dailies: Mapped[list[SupplyFlowDaily]] = relationship(back_populates="instrument")
    risk_indicator_dailies: Mapped[list[RiskIndicatorDaily]] = relationship(back_populates="instrument")
    fundamental_ratios: Mapped[list[FundamentalRatio]] = relationship(back_populates="instrument")


class DailyPrice(TimestampMixin, Base):
    __tablename__ = "daily_prices"
    __table_args__ = (
        Index("ix_daily_prices_trade_date", "trade_date"),
        Index("ix_daily_prices_instrument_date", "instrument_id", "trade_date"),
        Index(
            "ix_daily_prices_provider_adj_instrument_date",
            "provider",
            "is_adjusted",
            "instrument_id",
            "trade_date",
        ),
        UniqueConstraint(
            "instrument_id",
            "trade_date",
            "provider",
            "is_adjusted",
            name="uq_daily_prices_identity",
        ),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    trade_date: Mapped[date] = mapped_column(Date)
    open_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    high_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    low_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    volume: Mapped[int] = mapped_column(BigInteger)
    trading_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    provider: Mapped[str] = mapped_column(String(40))
    is_adjusted: Mapped[bool] = mapped_column(Boolean, default=False)

    instrument: Mapped[Instrument] = relationship(back_populates="daily_prices")


class QuoteSnapshot(TimestampMixin, Base):
    __tablename__ = "quote_snapshots"
    __table_args__ = (
        Index("ix_quote_snapshots_snapshot_date", "snapshot_date"),
        Index("ix_quote_snapshots_instrument_date", "instrument_id", "snapshot_date"),
        UniqueConstraint(
            "instrument_id",
            "snapshot_date",
            "provider",
            name="uq_quote_snapshots_identity",
        ),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    snapshot_date: Mapped[date] = mapped_column(Date)
    provider: Mapped[str] = mapped_column(String(40))
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    trading_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    per: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    pbr: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    eps: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    bps: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    turnover_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    foreign_holding_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    foreign_net_buy_qty: Mapped[int | None] = mapped_column(BigInteger)
    program_net_buy_qty: Mapped[int | None] = mapped_column(BigInteger)
    high_52w: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    low_52w: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))

    instrument: Mapped[Instrument] = relationship(back_populates="quote_snapshots")


class SupplyFlowDaily(TimestampMixin, Base):
    __tablename__ = "supply_flow_dailies"
    __table_args__ = (
        Index("ix_supply_flow_dailies_trade_date", "trade_date"),
        Index("ix_supply_flow_dailies_instrument_date", "instrument_id", "trade_date"),
        UniqueConstraint(
            "instrument_id",
            "trade_date",
            "provider",
            name="uq_supply_flow_dailies_identity",
        ),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    trade_date: Mapped[date] = mapped_column(Date)
    provider: Mapped[str] = mapped_column(String(40))
    foreign_net_buy_qty: Mapped[int | None] = mapped_column(BigInteger)
    institution_net_buy_qty: Mapped[int | None] = mapped_column(BigInteger)
    pension_net_buy_qty: Mapped[int | None] = mapped_column(BigInteger)
    foreign_net_buy_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    institution_net_buy_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    pension_net_buy_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    individual_net_buy_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))

    instrument: Mapped[Instrument] = relationship(back_populates="supply_flow_dailies")


class RiskIndicatorDaily(TimestampMixin, Base):
    __tablename__ = "risk_indicator_dailies"
    __table_args__ = (
        Index("ix_risk_indicator_dailies_trade_date", "trade_date"),
        Index("ix_risk_indicator_dailies_instrument_date", "instrument_id", "trade_date"),
        UniqueConstraint(
            "instrument_id",
            "trade_date",
            "provider",
            name="uq_risk_indicator_dailies_identity",
        ),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    trade_date: Mapped[date] = mapped_column(Date)
    provider: Mapped[str] = mapped_column(String(40))
    short_sale_volume: Mapped[int | None] = mapped_column(BigInteger)
    short_sale_volume_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    short_sale_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    short_sale_value_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    margin_loan_balance: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    margin_loan_balance_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    margin_loan_new_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    margin_loan_redeem_amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    stock_loan_balance: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    stock_loan_balance_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    instrument: Mapped[Instrument] = relationship(back_populates="risk_indicator_dailies")


class FundamentalRatio(TimestampMixin, Base):
    __tablename__ = "fundamental_ratios"
    __table_args__ = (
        Index("ix_fundamental_ratios_period", "fiscal_period"),
        Index("ix_fundamental_ratios_instrument_period", "instrument_id", "fiscal_period"),
        UniqueConstraint(
            "instrument_id",
            "fiscal_period",
            "period_type",
            "provider",
            name="uq_fundamental_ratios_identity",
        ),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    fiscal_period: Mapped[str] = mapped_column(String(10))
    period_type: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(40))
    revenue_growth: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    operating_income_growth: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    net_income_growth: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    roe: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    roa: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    operating_margin: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    net_margin: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    free_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    dividends_paid: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    current_assets: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    current_liabilities: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    cash_and_cash_equivalents: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    ebitda: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    fcf_yield: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    ev_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    payout_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    current_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    dividend_growth: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    dividend_streak_years: Mapped[int | None] = mapped_column(Integer)
    dividend_stability_score: Mapped[int | None] = mapped_column(Integer)
    eps: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    sps: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    bps: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    reserve_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    debt_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    instrument: Mapped[Instrument] = relationship(back_populates="fundamental_ratios")


class DataImportJob(Base):
    __tablename__ = "data_import_jobs"
    __table_args__ = (Index("ix_data_import_jobs_provider", "provider"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    job_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst_naive, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    message: Mapped[str | None] = mapped_column(String(500))


class BrokerAuditLog(Base):
    __tablename__ = "broker_audit_logs"
    __table_args__ = (
        Index("ix_broker_audit_logs_created_at", "created_at"),
        Index("ix_broker_audit_logs_provider_action", "provider", "action"),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    environment: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30))
    request_json: Mapped[str] = mapped_column(Text)
    response_json: Mapped[str] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst_naive, server_default=func.now())


class UserStrategy(TimestampMixin, Base):
    __tablename__ = "user_strategies"
    __table_args__ = (
        Index("ix_user_strategies_code", "code"),
        UniqueConstraint("code", name="uq_user_strategies_code"),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(String(500))
    formula: Mapped[str] = mapped_column(Text)
    result_count: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BacktestRun(TimestampMixin, Base):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_runs_strategy_code", "strategy_code"),
        Index("ix_backtest_runs_created_at", "created_at"),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_code: Mapped[str] = mapped_column(String(80))
    strategy_name: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(60))
    start_year: Mapped[int] = mapped_column()
    end_year: Mapped[int] = mapped_column()
    initial_amount: Mapped[int] = mapped_column(BigInteger)
    final_amount: Mapped[int] = mapped_column(BigInteger)
    result_json: Mapped[str] = mapped_column(Text)


class StrategySelectionRun(TimestampMixin, Base):
    __tablename__ = "strategy_selection_runs"
    __table_args__ = (
        Index("ix_strategy_selection_runs_strategy_code", "strategy_code"),
        Index("ix_strategy_selection_runs_created_at", "created_at"),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_code: Mapped[str] = mapped_column(String(80))
    strategy_name: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(200))
    result_count: Mapped[int] = mapped_column(Integer)
    result_json: Mapped[str] = mapped_column(Text)


class DataStatusSnapshot(Base):
    """data_status/data_quality의 대용량 daily_prices 집계를 사전 계산해 저장하는 요약 테이블.

    OHLCV 무결성 검사(컬럼 간 OR 비교)와 커버리지 HAVING 집계는 인덱스로 못 푸는 전체 스캔이라
    매 요청 실시간 계산 시 수백 초가 걸린다. 이 스냅샷을 주기적으로 갱신하고 화면은 여기서 읽는다.
    """

    __tablename__ = "data_status_snapshots"
    __table_args__ = (
        Index("ix_data_status_snapshots_computed_at", "computed_at"),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst_naive, server_default=func.now())
    daily_price_count: Mapped[int] = mapped_column(BigInteger, default=0)
    covered_symbol_count: Mapped[int] = mapped_column(Integer, default=0)
    invalid_ohlcv_count: Mapped[int] = mapped_column(BigInteger, default=0)
    # provider별 건수를 [[provider, count], ...] JSON 문자열로 저장한다.
    provider_counts_json: Mapped[str] = mapped_column(Text, default="[]")
