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


class DailyPrice(TimestampMixin, Base):
    __tablename__ = "daily_prices"
    __table_args__ = (
        Index("ix_daily_prices_trade_date", "trade_date"),
        Index("ix_daily_prices_instrument_date", "instrument_id", "trade_date"),
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
