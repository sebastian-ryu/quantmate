from __future__ import annotations

import json
import math
import os
import threading
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from quantmate_api.backtest_engine import (
    backtest_policy_for_strategy,
    build_daily_price_backtest,
    build_sample_backtest,
)
from quantmate_api.db import SessionLocal
from quantmate_api.kis_realtime import kis_realtime_quote_service
from quantmate_api.market_calendar import market_calendar_range, previous_market_trading_day
from quantmate_api.market_data import (
    MarketDataProviderUnavailable,
    default_krx_base_date,
    fetch_kis_buyable_cash,
    fetch_kis_current_price,
    fetch_kis_daily_credit_balance,
    fetch_kis_daily_order_executions,
    fetch_kis_daily_prices,
    fetch_kis_daily_short_sale,
    fetch_kis_domestic_balance,
    fetch_kis_financial_ratios,
    fetch_kis_investor_trade_daily,
    fetch_kis_market_cap_ranking,
    fetch_krx_daily_prices,
    fetch_krx_instruments,
    fetch_krx_market_daily_prices,
    fetch_open_dart_corp_codes,
    fetch_open_dart_financial_statements,
    fetch_yahoo_daily_prices,
    fetch_yfinance_symbol_daily_prices,
    get_kis_environment_name,
    get_kis_token_status,
    get_kis_ws_approval_key,
    get_kis_ws_approval_status,
    get_market_metadata,
    get_open_dart_corp_code_cache_status,
    has_kis_account_credentials,
    is_kis_open_api_ready,
    is_kis_paper_trading,
    is_open_dart_ready,
    mask_kis_account,
    normalize_market_code,
    normalize_yahoo_symbol,
    summarize_open_dart_financial_statements,
    submit_kis_domestic_cash_order,
)
from quantmate_api.models import (
    BacktestRun,
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
    UserStrategy,
)
from quantmate_api.providers import daily_price_provider_names, provider_status_rows
from quantmate_api.strategy_engine import (
    apply_candidate_quality_filters,
    apply_user_strategy_formula,
    build_strategy_candidates,
    build_strategy_candidates_from_daily_prices,
    enrich_strategy_candidates_with_fundamentals,
    enrich_strategy_candidates_with_quote_snapshots,
    enrich_strategy_candidates_with_risk_indicators,
    enrich_strategy_candidates_with_supply_flows,
    refresh_candidate_scores,
)
from quantmate_api.time_utils import now_kst_naive, today_kst


MANUAL_DATA_REFRESH_JOBS: dict[str, dict[str, object]] = {}
MANUAL_DATA_REFRESH_LOCK = threading.Lock()


class AppMode(StrEnum):
    RESEARCH = "research"
    LIVE_READONLY = "live-readonly"
    LIVE_TRADING = "live-trading"


class HealthResponse(BaseModel):
    status: str
    app: str
    mode: AppMode
    live_trading_enabled: bool


class StrategyPerformanceWindow(BaseModel):
    label: str
    years: int
    start_year: int
    end_year: int
    cagr: float | None = None
    total_return: float | None = None
    mdd: float | None = None
    final_amount: int | None = None
    status: str
    note: str


class StrategyPerformanceSnapshot(BaseModel):
    as_of: date
    data_as_of: date | None = None
    source: str
    initial_amount: int
    windows: list[StrategyPerformanceWindow]
    update_policy: str
    note: str


class StrategyPerformanceResponse(BaseModel):
    strategy_code: str
    performance: StrategyPerformanceSnapshot


class Strategy(BaseModel):
    code: str
    name: str
    source_type: str = "system"
    category: str
    style: str
    holding_period: str
    summary: str
    rebalance_rule: str
    data_requirements: list[str]
    universe_filter: list[str]
    signal_rules: list[str]
    ranking_rules: list[str]
    risk_controls: list[str]
    risk_notes: list[str]
    backtest_assumptions: list[str]
    references: list[str]
    performance: StrategyPerformanceSnapshot | None = None
    default_enabled: bool = True


class Recommendation(BaseModel):
    symbol: str
    name: str
    market: str
    strategy_code: str
    score: int = Field(ge=0, le=100)
    signal: str
    rationale: list[str]
    risk_flags: list[str]


class StrategyCandidate(BaseModel):
    symbol: str
    name: str
    exchange: str
    sector: str
    industry: str
    market_cap: float
    price: int
    change_pct: float
    per: float
    pbr: float
    roe: float
    revenue_growth: float
    foreign_net_buy_5d: int
    institution_net_buy_5d: int
    supply_score: int
    short_sale_ratio: float
    momentum: int
    strategy_score: int = Field(ge=0, le=100)
    rationale: list[str]
    risk_flags: list[str]
    trading_value_krw_100m: float = 0
    avg_volume_20d_10k: float = 0
    turnover_pct: float = 0
    psr: float = 0
    ev_ebitda: float = 0
    fcf_yield: float = 0
    dividend_yield: float = 0
    payout_ratio: float = 0
    dividend_growth: float = 0
    dividend_streak_years: int = 0
    dividend_stability_score: int = Field(default=0, ge=0, le=100)
    roa: float = 0
    operating_margin: float = 0
    net_margin: float = 0
    debt_ratio: float = 0
    current_ratio: float = 0
    eps_growth: float = 0
    operating_income_growth: float = 0
    beta: float = 0
    volatility_20d: float = 0
    drawdown_52w: float = 0
    rsi14: float = 0
    close_vs_ma20_pct: float = 0
    close_vs_ma60_pct: float = 0
    volume_surge: float = 0
    fair_value_upside: float = 0
    foreign_net_buy_20d: int = 0
    institution_net_buy_20d: int = 0
    pension_net_buy_20d: int = 0
    program_net_buy_5d: int = 0
    consecutive_foreign_buy_days: int = 0
    margin_debt_change_5d: float = 0


class DataFreshnessResponse(BaseModel):
    latest_daily_price_date: date | None = None
    expected_daily_price_date: date | None = None
    daily_price_status: str = "unknown"
    daily_price_providers: list[str] = Field(default_factory=list)
    latest_quote_snapshot_date: date | None = None
    latest_supply_flow_date: date | None = None
    latest_risk_indicator_date: date | None = None
    latest_fundamental_period: str | None = None
    message: str
    warnings: list[str] = Field(default_factory=list)


class StrategyCandidateResponse(BaseModel):
    run_id: int | None = None
    run_at: datetime | None = None
    strategy_code: str
    strategy_name: str
    source: str
    data_freshness: DataFreshnessResponse
    candidates: list[StrategyCandidate]


class StrategyExecutionModeContract(BaseModel):
    code: str
    label: str
    enabled: bool
    endpoint: str
    note: str


class BacktestPolicyResponse(BaseModel):
    rebalance_interval_months: int
    rebalance_label: str
    rebalance_timing: str
    return_price_basis: str
    holding_count: int
    weighting_method: str
    rebalance_amount_rule: str
    initial_rebalance_amount: int | None = None
    trading_cost_pct: float
    slippage_pct: float


class StrategyExecutionContractResponse(BaseModel):
    strategy_code: str
    strategy_name: str
    source_type: str
    summary: str
    formula: str
    provider_priority: list[str]
    backtest_policy: BacktestPolicyResponse
    safety_controls: list[str]
    modes: list[StrategyExecutionModeContract]


class StrategySelectionRunSummary(BaseModel):
    id: int
    strategy_code: str
    strategy_name: str
    source: str
    result_count: int
    top_candidates: str
    created_at: datetime


class ScreenerSearchRequest(BaseModel):
    strategy_code: str = "relative-momentum-swing"
    formula: str = ""
    limit: int = Field(default=50, ge=1, le=100)


class ScreenerSearchResponse(BaseModel):
    strategy_code: str
    strategy_name: str
    source: str
    data_freshness: DataFreshnessResponse
    unsupported_conditions: list[str]
    candidates: list[StrategyCandidate]


class UserStrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    formula: str = Field(min_length=1, max_length=5000)
    result_count: int = Field(ge=0)


class UserStrategyResponse(BaseModel):
    id: int
    code: str
    name: str
    summary: str
    formula: str
    result_count: int
    created_at: datetime


class BacktestMetric(BaseModel):
    label: str
    value: str
    tone: str


class EquityPoint(BaseModel):
    day: str
    value: float


class BacktestPreview(BaseModel):
    strategy_code: str
    period: str
    assumptions: list[str]
    metrics: list[BacktestMetric]
    equity_curve: list[EquityPoint]


class BacktestRunRequest(BaseModel):
    strategy_code: str
    start_year: int = Field(ge=1990, le=2100)
    end_year: int = Field(ge=1990, le=2100)
    initial_amount: int = Field(gt=0)
    benchmark_code: str = "kospi200"
    rebalance_interval_months: int | None = Field(default=None, ge=1, le=12)
    holding_count: int | None = Field(default=None, ge=1, le=50)


class BacktestPerformanceMetric(BaseModel):
    metric: str
    value: str


class BacktestAnnualReturn(BaseModel):
    year: str
    portfolio_return: float
    yield_pct: float
    balance: int
    income: int


class BacktestEquityPoint(BaseModel):
    label: str
    portfolio: int


class BacktestBenchmarkPoint(BaseModel):
    label: str
    benchmark: int


class BacktestRebalanceRow(BaseModel):
    date: str
    holdings: str
    entries: str
    exits: str
    turnover: str


class BacktestRunResponse(BaseModel):
    run_id: int | None = None
    strategy_code: str
    strategy_name: str
    source: str
    period: str
    initial_amount: int
    final_amount: int
    run_at: str
    notice: str
    benchmark_code: str = "none"
    benchmark_name: str = ""
    benchmark_curve: list[BacktestBenchmarkPoint] = Field(default_factory=list)
    backtest_policy: BacktestPolicyResponse
    metrics: list[BacktestPerformanceMetric]
    annual_returns: list[BacktestAnnualReturn]
    equity_curve: list[BacktestEquityPoint]
    rebalance_history: list[BacktestRebalanceRow]


class BacktestRunSummary(BaseModel):
    id: int
    strategy_code: str
    strategy_name: str
    period: str
    source: str
    initial_amount: int
    final_amount: int
    created_at: datetime


class DashboardResponse(BaseModel):
    as_of: date
    modes: list[dict[str, str | bool]]
    strategies: list[Strategy]
    recommendations: list[Recommendation]
    backtest: BacktestPreview


class DataStatusResponse(BaseModel):
    connected: bool
    provider_status: list[dict[str, str | bool]]
    table_counts: dict[str, int]
    message: str


class DataQualityCheck(BaseModel):
    code: str
    label: str
    status: str
    value: str
    message: str


class DataQualityResponse(BaseModel):
    generated_at: datetime
    summary_status: str
    checks: list[DataQualityCheck]


class ManualDataRefreshRequest(BaseModel):
    refresh_instruments: bool = True
    refresh_daily_prices: bool = True
    markets: list[str] = Field(default_factory=lambda: ["KOSPI", "KOSDAQ"], max_length=3)
    lookback_days: int = Field(default=10, ge=1, le=365)


class ManualDataRefreshJobResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    progress_pct: int
    current_step: int
    total_steps: int
    success_count: int = 0
    failed_count: int = 0
    saved_count: int = 0
    started_at: datetime
    finished_at: datetime | None = None
    elapsed_seconds: int = 0
    estimated_remaining_seconds: int | None = None
    latest_daily_price_date: date | None = None
    expected_daily_price_date: date | None = None
    message: str
    warnings: list[str] = Field(default_factory=list)


class MarketCalendarDayResponse(BaseModel):
    date: date
    market: str
    is_open: bool
    reason: str


class MarketCalendarResponse(BaseModel):
    market: str
    timezone: str
    start: date
    end: date
    open_days: int
    closed_days: int
    items: list[MarketCalendarDayResponse]


class KrxInstrumentPreview(BaseModel):
    symbol: str
    name: str
    exchange: str
    asset_type: str


class KrxInstrumentPreviewResponse(BaseModel):
    provider: str
    market: str
    base_date: str
    count: int
    instruments: list[KrxInstrumentPreview]


class KrxInstrumentImportRequest(BaseModel):
    market: str = Field(default="ALL", max_length=20)
    limit: int = Field(default=3000, ge=1, le=3000)
    base_date: str | None = Field(default=None, max_length=8)


class KrxInstrumentImportResponse(BaseModel):
    provider: str
    job_id: int
    market: str
    base_date: str
    fetched_count: int
    created_count: int
    updated_count: int
    skipped_count: int
    instrument_count: int
    message: str


class YahooDailyPrice(BaseModel):
    symbol: str
    trade_date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    adjusted_close: float | None
    volume: int | None
    provider: str


class KrxDailyPricePreviewResponse(BaseModel):
    provider: str
    symbol: str
    exchange: str
    count: int
    prices: list[YahooDailyPrice]


class KisTokenStatusResponse(BaseModel):
    provider: str
    ready: bool
    environment: str
    base_url: str
    token_cached: bool
    expires_in_seconds: int


class KisWebSocketApprovalStatusResponse(BaseModel):
    provider: str
    ready: bool
    environment: str
    base_url: str
    ws_url: str
    approval_key_cached: bool
    expires_in_seconds: int


class KisWebSocketApprovalIssueRequest(BaseModel):
    force_refresh: bool = False


class KisRealtimeQuoteResponse(BaseModel):
    symbol: str
    trade_time: str
    price: int | None = None
    change: int | None = None
    change_rate: float | None = None
    trade_volume: int | None = None
    accumulated_volume: int | None = None
    accumulated_trading_value: int | None = None
    bid_price: int | None = None
    ask_price: int | None = None
    received_at: str
    raw_tr_id: str


class KisRealtimeQuoteStatusResponse(BaseModel):
    provider: str
    environment: str
    ws_url: str
    running: bool
    connected: bool
    subscribed_symbols: list[str]
    quote_count: int
    last_message_at: str | None = None
    last_error: str


class KisRealtimeQuoteSubscribeRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=50)


class OpenDartCorpCodeCacheStatusResponse(BaseModel):
    provider: str
    ready: bool
    base_url: str
    cache_path: str
    cached: bool
    cached_count: int
    fetched_at: str


class OpenDartCorpCodeCacheResponse(BaseModel):
    provider: str
    fetched_count: int
    listed_count: int
    cache_path: str
    message: str


class OpenDartFinancialStatementItem(BaseModel):
    provider: str
    symbol: str
    corp_code: str
    corp_name: str
    business_year: int
    report_code: str
    fs_div: str
    receipt_no: str
    statement_type: str
    statement_name: str
    account_id: str
    account_name: str
    account_detail: str
    current_term_name: str
    current_amount: int | None = None
    current_accumulated_amount: int | None = None
    previous_term_name: str
    previous_amount: int | None = None
    previous_accumulated_amount: int | None = None
    currency: str


class OpenDartFinancialSummaryResponse(BaseModel):
    revenue: int | None = None
    operating_income: int | None = None
    net_income: int | None = None
    assets: int | None = None
    liabilities: int | None = None
    equity: int | None = None
    current_assets: int | None = None
    current_liabilities: int | None = None
    operating_cash_flow: int | None = None
    capex: int | None = None
    cash_and_cash_equivalents: int | None = None
    depreciation_amortization: int | None = None
    ebitda: int | None = None
    dividends_paid: int | None = None
    free_cash_flow: int | None = None
    dividend_growth: float | None = None
    revenue_growth: float | None = None
    operating_income_growth: float | None = None
    net_income_growth: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    debt_ratio: float | None = None
    current_ratio: float | None = None
    roe: float | None = None
    roa: float | None = None


class OpenDartFinancialStatementResponse(BaseModel):
    provider: str
    symbol: str
    business_year: int
    report_code: str
    fs_div: str
    count: int
    summary: OpenDartFinancialSummaryResponse
    items: list[OpenDartFinancialStatementItem]


class OpenDartFinancialStatementImportResponse(BaseModel):
    provider: str
    symbol: str
    business_year: int
    report_code: str
    fs_div: str
    count: int
    saved_count: int
    summary: OpenDartFinancialSummaryResponse


class KisBrokerAccountStatusResponse(BaseModel):
    provider: str
    ready: bool
    environment: str
    account_configured: bool
    account_label: str
    paper_trading_enabled: bool
    live_trading_enabled: bool
    message: str


class KisTradingSafetyStatusResponse(BaseModel):
    provider: str
    ready: bool
    environment: str
    account_label: str
    paper_trading_enabled: bool
    live_trading_enabled: bool
    emergency_stop_enabled: bool
    manual_confirmation_required: bool
    daily_loss_stop_enabled: bool
    max_order_amount_krw: int
    max_daily_order_count: int
    max_daily_loss_krw: int
    remaining_daily_order_count: int | None
    can_submit_paper_orders: bool
    can_submit_live_orders: bool
    message: str
    warnings: list[str]


class KisBrokerBalanceSummary(BaseModel):
    deposit_amount: int = 0
    next_settlement_amount: int = 0
    purchase_amount: int = 0
    evaluation_amount: int = 0
    profit_loss_amount: int = 0
    profit_loss_rate: float = 0
    securities_evaluation_amount: int = 0
    total_evaluation_amount: int = 0
    net_asset_amount: int = 0
    total_loan_amount: int = 0
    previous_total_asset_evaluation_amount: int = 0
    asset_change_amount: int = 0
    asset_change_rate: float = 0


class KisBrokerHolding(BaseModel):
    symbol: str
    name: str
    trade_type: str = ""
    holding_quantity: int = 0
    orderable_quantity: int = 0
    average_price: int = 0
    purchase_amount: int = 0
    current_price: int = 0
    evaluation_amount: int = 0
    profit_loss_amount: int = 0
    profit_loss_rate: float = 0
    evaluation_earning_rate: float = 0
    change_rate: float = 0


class KisBrokerBalanceResponse(BaseModel):
    provider: str
    environment: str
    account_label: str
    fetched_at: str
    summary: KisBrokerBalanceSummary
    holdings: list[KisBrokerHolding]


class KisBuyableCashResponse(BaseModel):
    provider: str
    environment: str
    symbol: str
    orderable_cash: int = 0
    orderable_substitute: int = 0
    reusable_amount: int = 0
    calculation_unit_price: int = 0
    cash_buy_amount: int = 0
    cash_buy_quantity: int = 0
    max_buy_amount: int = 0
    max_buy_quantity: int = 0
    cma_evaluation_amount: int = 0


class KisOrderExecutionItem(BaseModel):
    order_date: str
    order_time: str
    order_branch_no: str
    order_no: str
    original_order_no: str = ""
    symbol: str
    name: str
    side_code: str = ""
    side_name: str = ""
    order_type_name: str = ""
    order_type_code: str = ""
    ordered_quantity: int = 0
    order_price: int = 0
    filled_quantity: int = 0
    average_price: int = 0
    filled_amount: int = 0
    remaining_quantity: int = 0
    rejected_quantity: int = 0
    canceled: bool = False
    status: str = ""
    execution_condition: str = ""
    exchange_code: str = ""


class KisOrderExecutionSummary(BaseModel):
    total_order_quantity: int = 0
    total_filled_quantity: int = 0
    total_filled_amount: int = 0
    estimated_fee_total: int = 0
    purchase_average_price: int = 0


class KisOrderExecutionResponse(BaseModel):
    provider: str
    environment: str
    account_label: str
    start_date: str
    end_date: str
    summary: KisOrderExecutionSummary
    orders: list[KisOrderExecutionItem]


class KisPaperOrderRequest(BaseModel):
    side: str = Field(pattern="^(buy|sell)$")
    symbol: str = Field(min_length=1, max_length=20)
    quantity: int = Field(ge=1)
    order_type: str = Field(default="market", pattern="^(market|limit)$")
    price: int = Field(default=0, ge=0)
    exchange_id: str = Field(default="KRX", max_length=10)
    confirm_submit: bool = False
    confirm_phrase: str = ""


class KisPaperOrderResponse(BaseModel):
    provider: str
    environment: str
    symbol: str
    side: str
    order_type: str
    quantity: int
    price: int
    order_no: str
    order_time: str
    exchange_order_org_no: str
    message: str
    audit_log_id: int | None = None


class KisOrderProposalRequest(BaseModel):
    strategy_code: str = Field(min_length=1, max_length=120)
    max_positions: int = Field(default=10, ge=1, le=30)
    amount_per_symbol: int = Field(default=5_000_000, ge=1_000, le=1_000_000_000)
    order_type: str = Field(default="market", pattern="^(market|limit)$")
    cash_buffer_rate: float = Field(default=0, ge=0, le=50)


class KisOrderProposalLine(BaseModel):
    symbol: str
    name: str
    side: str = "buy"
    order_type: str
    reference_price: int
    quantity: int
    estimated_amount: int
    strategy_score: int
    status: str
    warnings: list[str]
    rationale: list[str]


class KisOrderProposalResponse(BaseModel):
    provider: str
    environment: str
    account_label: str
    proposal_id: str
    generated_at: str
    strategy_code: str
    strategy_name: str
    source: str
    max_positions: int
    amount_per_symbol: int
    order_type: str
    cash_buffer_rate: float
    available_cash: int
    cash_buffer_amount: int
    total_estimated_amount: int
    executable_count: int
    warnings: list[str]
    lines: list[KisOrderProposalLine]
    audit_log_id: int | None = None


class KisPaperBatchOrderItem(BaseModel):
    side: str = Field(default="buy", pattern="^(buy|sell)$")
    symbol: str = Field(min_length=1, max_length=20)
    name: str = Field(default="", max_length=120)
    quantity: int = Field(ge=1)
    order_type: str = Field(default="market", pattern="^(market|limit)$")
    price: int = Field(default=0, ge=0)
    exchange_id: str = Field(default="KRX", max_length=10)


class KisPaperBatchOrderRequest(BaseModel):
    orders: list[KisPaperBatchOrderItem] = Field(min_length=1, max_length=20)
    confirm_submit: bool = False
    confirm_phrase: str = ""


class KisPaperBatchOrderResult(BaseModel):
    symbol: str
    name: str
    side: str
    order_type: str
    quantity: int
    price: int
    estimated_amount: int
    status: str
    order_no: str = ""
    order_time: str = ""
    message: str


class KisPaperBatchOrderResponse(BaseModel):
    provider: str
    environment: str
    account_label: str
    batch_id: str
    submitted_count: int
    failed_count: int
    total_estimated_amount: int
    status: str
    results: list[KisPaperBatchOrderResult]
    before_audit_log_id: int | None = None
    after_audit_log_id: int | None = None


class KisCurrentPriceResponse(BaseModel):
    provider: str
    symbol: str
    name: str
    price: int | None
    change: int | None
    change_rate: float | None
    volume: int | None
    trading_value: int | None
    open: int | None
    high: int | None
    low: int | None
    market_state: str
    market_cap: int | None = None
    per: float | None = None
    pbr: float | None = None
    eps: float | None = None
    bps: float | None = None
    turnover_pct: float | None = None
    foreign_holding_rate: float | None = None
    foreign_net_buy_qty: int | None = None
    program_net_buy_qty: int | None = None
    high_52w: int | None = None
    low_52w: int | None = None


class YahooDailyPricePreviewResponse(BaseModel):
    provider: str
    symbol: str
    yahoo_symbol: str
    exchange: str
    count: int
    prices: list[YahooDailyPrice]


class KisDailyPricePreviewResponse(BaseModel):
    provider: str
    symbol: str
    count: int
    prices: list[YahooDailyPrice]


class KisMarketCapRankingItem(BaseModel):
    provider: str
    symbol: str
    name: str
    exchange: str
    price: int | None = None
    change_rate: float | None = None
    volume: int | None = None
    market_cap: int | None = None
    listed_shares: int | None = None
    market_cap_weight: float | None = None
    rank: int | None = None


class KisMarketCapRankingResponse(BaseModel):
    provider: str
    count: int
    items: list[KisMarketCapRankingItem]


class KisInstrumentImportRequest(BaseModel):
    market: str = Field(default="ALL", max_length=20)
    limit: int = Field(default=100, ge=1, le=100)


class KisInstrumentImportResponse(BaseModel):
    provider: str
    job_id: int
    market: str
    fetched_count: int
    created_count: int
    updated_count: int
    skipped_count: int
    instrument_count: int
    message: str


class KisInvestorTradeDailyItem(BaseModel):
    provider: str
    symbol: str
    trade_date: date
    foreign_net_buy_qty: int | None = None
    institution_net_buy_qty: int | None = None
    pension_net_buy_qty: int | None = None
    foreign_net_buy_value: int | None = None
    institution_net_buy_value: int | None = None
    pension_net_buy_value: int | None = None
    individual_net_buy_value: int | None = None


class KisInvestorTradeDailyResponse(BaseModel):
    provider: str
    symbol: str
    count: int
    items: list[KisInvestorTradeDailyItem]


class KisDailyShortSaleItem(BaseModel):
    provider: str
    symbol: str
    trade_date: date
    short_sale_volume: int | None = None
    short_sale_volume_ratio: float | None = None
    short_sale_value: int | None = None
    short_sale_value_ratio: float | None = None


class KisDailyShortSaleResponse(BaseModel):
    provider: str
    symbol: str
    count: int
    items: list[KisDailyShortSaleItem]


class KisDailyCreditBalanceItem(BaseModel):
    provider: str
    symbol: str
    trade_date: date
    margin_loan_balance: int | None = None
    margin_loan_balance_rate: float | None = None
    margin_loan_new_amount: int | None = None
    margin_loan_redeem_amount: int | None = None
    stock_loan_balance: int | None = None
    stock_loan_balance_rate: float | None = None


class KisDailyCreditBalanceResponse(BaseModel):
    provider: str
    symbol: str
    count: int
    items: list[KisDailyCreditBalanceItem]


class KisFinancialRatioItem(BaseModel):
    provider: str
    symbol: str
    fiscal_period: str
    period_type: str
    revenue_growth: float | None = None
    operating_income_growth: float | None = None
    net_income_growth: float | None = None
    roe: float | None = None
    roa: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    eps: float | None = None
    sps: float | None = None
    bps: float | None = None
    reserve_ratio: float | None = None
    debt_ratio: float | None = None


class KisFinancialRatioResponse(BaseModel):
    provider: str
    symbol: str
    period_type: str
    count: int
    items: list[KisFinancialRatioItem]


class YahooDailyPriceImportRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    name: str | None = Field(default=None, max_length=200)
    exchange: str = Field(default="KOSPI", max_length=40)
    start: date | None = None
    end: date | None = None
    is_adjusted: bool = False


class YahooDailyPriceImportResponse(BaseModel):
    provider: str
    job_id: int
    symbol: str
    yahoo_symbol: str
    exchange: str
    fetched_count: int
    saved_count: int
    message: str


class KrxDailyPriceImportRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    name: str | None = Field(default=None, max_length=200)
    exchange: str = Field(default="KOSPI", max_length=40)
    start: date | None = None
    end: date | None = None


class KrxDailyPriceImportResponse(BaseModel):
    provider: str
    job_id: int
    symbol: str
    exchange: str
    fetched_count: int
    saved_count: int
    message: str


class KrxMarketDailyPriceImportRequest(BaseModel):
    market: str = Field(default="KOSPI", max_length=20)
    start: date
    end: date


class KrxMarketDailyPriceImportResponse(BaseModel):
    provider: str
    job_id: int
    market: str
    start: date
    end: date
    fetched_count: int
    saved_count: int
    message: str


class KrxDailyPriceBatchImportRequest(BaseModel):
    strategy_code: str = "relative-momentum-swing"
    start: date | None = None
    end: date | None = None
    max_symbols: int = Field(default=5, ge=1, le=10)


class KrxDailyPriceBatchImportItem(BaseModel):
    symbol: str
    name: str
    exchange: str
    status: str
    saved_count: int
    message: str


class KrxDailyPriceBatchImportResponse(BaseModel):
    provider: str
    strategy_code: str
    requested_symbols: int
    success_count: int
    failed_count: int
    saved_count: int
    items: list[KrxDailyPriceBatchImportItem]


class KisDailyPriceImportRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    name: str | None = Field(default=None, max_length=200)
    exchange: str = Field(default="KOSPI", max_length=40)
    start: date | None = None
    end: date | None = None
    is_adjusted: bool = False


class KisDailyPriceImportResponse(BaseModel):
    provider: str
    job_id: int
    symbol: str
    exchange: str
    fetched_count: int
    saved_count: int
    message: str


class KisDailyPriceBatchImportRequest(BaseModel):
    strategy_code: str = "relative-momentum-swing"
    start: date | None = None
    end: date | None = None
    max_symbols: int = Field(default=5, ge=1, le=10)
    is_adjusted: bool = False


class KisDailyPriceBatchImportItem(BaseModel):
    symbol: str
    name: str
    exchange: str
    status: str
    saved_count: int
    message: str


class KisDailyPriceBatchImportResponse(BaseModel):
    provider: str
    strategy_code: str
    requested_symbols: int
    success_count: int
    failed_count: int
    saved_count: int
    items: list[KisDailyPriceBatchImportItem]


class YahooDailyPriceBatchImportRequest(BaseModel):
    strategy_code: str = "relative-momentum-swing"
    start: date | None = None
    end: date | None = None
    max_symbols: int = Field(default=10, ge=1, le=30)
    is_adjusted: bool = False


class YahooDailyPriceBatchImportItem(BaseModel):
    symbol: str
    name: str
    exchange: str
    status: str
    saved_count: int
    message: str


class YahooDailyPriceBatchImportResponse(BaseModel):
    provider: str
    strategy_code: str
    requested_symbols: int
    success_count: int
    failed_count: int
    saved_count: int
    items: list[YahooDailyPriceBatchImportItem]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _json_dumps(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _paper_trading_enabled() -> bool:
    return _env_bool("PAPER_TRADING_ENABLED", default=False)


def _live_trading_enabled() -> bool:
    return _env_bool("LIVE_TRADING_ENABLED", default=False)


def _emergency_stop_enabled() -> bool:
    return _env_bool("EMERGENCY_STOP_ENABLED", default=False)


def _manual_order_confirmation_required() -> bool:
    return _env_bool("MANUAL_ORDER_CONFIRMATION_REQUIRED", default=True)


def _daily_loss_stop_enabled() -> bool:
    return _env_bool("DAILY_LOSS_STOP_ENABLED", default=False)


def _max_order_amount_krw() -> int:
    return _env_int("MAX_ORDER_AMOUNT_KRW", 5_000_000)


def _max_daily_order_count() -> int:
    return _env_int("MAX_DAILY_ORDER_COUNT", 10)


def _max_daily_loss_krw() -> int:
    return _env_int("MAX_DAILY_LOSS_KRW", 50_000)


def _kis_current_quote_max_age_minutes() -> int:
    return max(0, _env_int("KIS_CURRENT_QUOTE_MAX_AGE_MINUTES", 10))


def _kis_current_quote_refresh_max_symbols() -> int:
    return max(1, min(_env_int("KIS_CURRENT_QUOTE_REFRESH_MAX_SYMBOLS", 30), 100))


def _strategy_daily_price_max_staleness_days() -> int:
    return max(0, _env_int("STRATEGY_DAILY_PRICE_MAX_STALENESS_DAYS", 1))


def _masked_kis_account_label() -> str:
    account_no = os.getenv("KIS_ACCOUNT_NO", "").strip()
    product_code = os.getenv("KIS_ACCOUNT_PRODUCT_CODE", "").strip()
    if not account_no or not product_code:
        return ""
    return mask_kis_account(account_no=account_no, product_code=product_code)


def _create_broker_audit_log(
    *,
    action: str,
    status: str,
    request_payload: dict[str, object],
    response_payload: dict[str, object],
    message: str | None = None,
) -> int:
    with SessionLocal() as session:
        log = BrokerAuditLog(
            provider="KIS Open API",
            environment=get_kis_environment_name(),
            action=action,
            status=status,
            request_json=_json_dumps(request_payload),
            response_json=_json_dumps(response_payload),
            message=message,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        return log.id


def _try_create_broker_audit_log(
    *,
    action: str,
    status: str,
    request_payload: dict[str, object],
    response_payload: dict[str, object],
    message: str | None = None,
) -> int | None:
    try:
        return _create_broker_audit_log(
            action=action,
            status=status,
            request_payload=request_payload,
            response_payload=response_payload,
            message=message,
        )
    except SQLAlchemyError:
        return None


def _count_today_successful_paper_orders() -> int:
    today_start = datetime.combine(today_kst(), datetime.min.time())
    with SessionLocal() as session:
        single_order_count = (
            session.scalar(
                select(func.count())
                .select_from(BrokerAuditLog)
                .where(
                    BrokerAuditLog.environment == "paper",
                    BrokerAuditLog.action == "paper_order.submit.after",
                    BrokerAuditLog.status == "success",
                    BrokerAuditLog.created_at >= today_start,
                )
            )
            or 0
        )
        batch_logs = session.scalars(
            select(BrokerAuditLog).where(
                BrokerAuditLog.environment == "paper",
                BrokerAuditLog.action == "paper_batch_order.submit.after",
                BrokerAuditLog.status.in_(["success", "partial_failed"]),
                BrokerAuditLog.created_at >= today_start,
            )
        ).all()
        batch_count = 0
        for log in batch_logs:
            try:
                payload = json.loads(log.response_json or "{}")
            except json.JSONDecodeError:
                continue
            batch_count += int(payload.get("submitted_count") or 0)

        return single_order_count + batch_count


def _estimate_order_amount(request: KisPaperOrderRequest) -> int:
    if request.order_type == "limit":
        return request.quantity * request.price

    quote = fetch_kis_current_price(symbol=request.symbol)
    price = int(quote.get("price") or 0)
    if price <= 0:
        raise MarketDataProviderUnavailable("시장가 주문 한도 계산에 필요한 현재가를 확인하지 못했습니다.")
    return request.quantity * price


def _validate_paper_order_risk_limits(request: KisPaperOrderRequest) -> int:
    estimated_amount = _estimate_order_amount(request)
    max_order_amount = _max_order_amount_krw()
    if max_order_amount > 0 and estimated_amount > max_order_amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"주문 예상금액 {estimated_amount:,}원이 1회 주문 한도 "
                f"{max_order_amount:,}원을 초과합니다."
            ),
        )

    max_daily_count = _max_daily_order_count()
    if max_daily_count > 0 and _count_today_successful_paper_orders() >= max_daily_count:
        raise HTTPException(
            status_code=400,
            detail=f"오늘 모의주문 횟수가 일일 한도 {max_daily_count}회를 초과했습니다.",
        )

    return estimated_amount


def _validate_paper_batch_order_risk_limits(
    orders: list[KisPaperBatchOrderItem],
) -> list[tuple[KisPaperBatchOrderItem, int]]:
    max_order_amount = _max_order_amount_krw()
    estimated_orders: list[tuple[KisPaperBatchOrderItem, int]] = []

    for order in orders:
        single_request = KisPaperOrderRequest(
            side=order.side,
            symbol=order.symbol,
            quantity=order.quantity,
            order_type=order.order_type,
            price=order.price,
            exchange_id=order.exchange_id,
            confirm_submit=True,
        )
        estimated_amount = _estimate_order_amount(single_request)
        if max_order_amount > 0 and estimated_amount > max_order_amount:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{order.symbol} 주문 예상금액 {estimated_amount:,}원이 1회 주문 한도 "
                    f"{max_order_amount:,}원을 초과합니다."
                ),
            )
        estimated_orders.append((order, estimated_amount))

    max_daily_count = _max_daily_order_count()
    if max_daily_count > 0:
        current_count = _count_today_successful_paper_orders()
        if current_count + len(orders) > max_daily_count:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"일괄 주문 {len(orders)}건을 제출하면 오늘 모의주문 횟수가 "
                    f"일일 한도 {max_daily_count}회를 초과합니다."
                ),
            )

    return estimated_orders


def _int_from_balance_summary(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _daily_loss_amount_from_balance(balance: dict[str, object]) -> int:
    summary = balance.get("summary")
    if not isinstance(summary, dict):
        return 0

    asset_change = _int_from_balance_summary(summary.get("asset_change_amount"))
    if asset_change is not None and asset_change < 0:
        return abs(asset_change)

    net_asset = _int_from_balance_summary(summary.get("net_asset_amount"))
    previous_asset = _int_from_balance_summary(summary.get("previous_total_asset_evaluation_amount"))
    if net_asset is not None and previous_asset is not None and previous_asset > 0 and net_asset < previous_asset:
        return previous_asset - net_asset

    return 0


def _validate_daily_loss_stop() -> int:
    if not _daily_loss_stop_enabled():
        return 0

    max_daily_loss = _max_daily_loss_krw()
    if max_daily_loss <= 0:
        return 0

    try:
        balance = fetch_kis_domestic_balance()
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=f"일일 손실 중지 확인을 위한 KIS 잔고 조회에 실패했습니다: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"일일 손실 중지 확인을 위한 KIS 계좌 설정 확인이 필요합니다: {exc}",
        ) from exc

    daily_loss = _daily_loss_amount_from_balance(balance)
    if daily_loss >= max_daily_loss:
        raise HTTPException(
            status_code=403,
            detail=f"오늘 손실 {daily_loss:,}원이 일일 손실 중지 한도 {max_daily_loss:,}원 이상입니다.",
        )

    return daily_loss


def _proposal_available_cash() -> tuple[int, bool, list[str]]:
    try:
        balance = fetch_kis_domestic_balance()
    except MarketDataProviderUnavailable as exc:
        return 0, False, [f"KIS 계좌 현금 조회 실패: {exc}"]
    except ValueError as exc:
        return 0, False, [f"KIS 계좌 설정 확인 필요: {exc}"]

    summary = balance.get("summary", {})
    if not isinstance(summary, dict):
        return 0, False, ["KIS 잔고 응답에서 예수금을 확인하지 못했습니다."]
    try:
        return int(summary.get("deposit_amount") or 0), True, []
    except (TypeError, ValueError):
        return 0, False, ["KIS 예수금 값을 숫자로 해석하지 못했습니다."]


def _remaining_daily_paper_order_slots() -> tuple[int | None, list[str]]:
    max_daily_count = _max_daily_order_count()
    if max_daily_count <= 0:
        return None, []

    try:
        used_count = _count_today_successful_paper_orders()
    except SQLAlchemyError as exc:
        return None, [f"일일 주문 횟수 조회 실패: {exc.__class__.__name__}"]

    return max(0, max_daily_count - used_count), []


def _trading_safety_status_response() -> KisTradingSafetyStatusResponse:
    api_ready = is_kis_open_api_ready()
    account_configured = has_kis_account_credentials()
    ready = api_ready and account_configured
    paper_mode = is_kis_paper_trading()
    paper_enabled = _paper_trading_enabled()
    live_enabled = _live_trading_enabled()
    emergency_stop = _emergency_stop_enabled()
    manual_confirmation_required = _manual_order_confirmation_required()
    daily_loss_stop = _daily_loss_stop_enabled()
    remaining_slots, slot_warnings = _remaining_daily_paper_order_slots()
    warnings = list(slot_warnings)

    if not api_ready:
        warnings.append("KIS App Key/Secret 설정이 필요합니다.")
    if not account_configured:
        warnings.append("KIS 계좌번호와 계좌상품코드 설정이 필요합니다.")
    if emergency_stop:
        warnings.append("긴급 중지 상태라 주문 제출을 차단합니다.")
    if not paper_mode:
        warnings.append("현재 KIS 실전 계좌 설정입니다. 실전 주문 API는 아직 열지 않았습니다.")
    elif not paper_enabled:
        warnings.append("PAPER_TRADING_ENABLED=false 상태라 모의주문 제출은 잠겨 있습니다.")
    if remaining_slots == 0:
        warnings.append("오늘 남은 모의주문 가능 횟수가 없습니다.")
    if daily_loss_stop:
        warnings.append("일일 손실 중지가 켜져 있어 주문 제출 직전에 KIS 잔고 기준 손실 한도를 확인합니다.")

    can_submit_paper_orders = ready and paper_mode and paper_enabled and not emergency_stop and remaining_slots != 0
    can_submit_live_orders = False
    if paper_mode:
        message = "모의주문 안전장치 상태입니다."
    else:
        message = "실전 계좌 읽기 상태입니다. 실전 주문 제출은 아직 비활성화되어 있습니다."

    return KisTradingSafetyStatusResponse(
        provider="KIS Open API",
        ready=ready,
        environment=get_kis_environment_name(),
        account_label=_masked_kis_account_label(),
        paper_trading_enabled=paper_enabled,
        live_trading_enabled=live_enabled,
        emergency_stop_enabled=emergency_stop,
        manual_confirmation_required=manual_confirmation_required,
        daily_loss_stop_enabled=daily_loss_stop,
        max_order_amount_krw=_max_order_amount_krw(),
        max_daily_order_count=_max_daily_order_count(),
        max_daily_loss_krw=_max_daily_loss_krw(),
        remaining_daily_order_count=remaining_slots,
        can_submit_paper_orders=can_submit_paper_orders,
        can_submit_live_orders=can_submit_live_orders,
        message=message,
        warnings=warnings,
    )


def _build_kis_order_proposal_lines(
    *,
    candidates: list[StrategyCandidate],
    request: KisOrderProposalRequest,
    available_cash: int,
    cash_verified: bool,
    remaining_daily_slots: int | None,
) -> tuple[list[KisOrderProposalLine], int, int, list[str]]:
    lines: list[KisOrderProposalLine] = []
    total_estimated_amount = 0
    executable_count = 0
    warnings: list[str] = []
    max_order_amount = _max_order_amount_krw()
    cash_budget = max(0, int(available_cash * (1 - request.cash_buffer_rate / 100))) if cash_verified else None
    remaining_cash = cash_budget

    for candidate in candidates[: request.max_positions]:
        line_warnings: list[str] = []
        reference_price = max(0, int(candidate.price or 0))
        quantity = request.amount_per_symbol // reference_price if reference_price > 0 else 0
        estimated_amount = quantity * reference_price
        status = "주문 가능"

        if reference_price <= 0:
            status = "현재가 없음"
            line_warnings.append("수량 계산에 필요한 현재가가 없습니다.")
        elif quantity <= 0:
            status = "금액 부족"
            line_warnings.append("종목당 금액이 현재가보다 작습니다.")

        if status == "주문 가능" and max_order_amount > 0 and estimated_amount > max_order_amount:
            status = "1회 한도 초과"
            line_warnings.append(f"예상금액이 1회 주문 한도 {max_order_amount:,}원을 초과합니다.")

        if status == "주문 가능" and remaining_daily_slots is not None and executable_count >= remaining_daily_slots:
            status = "일일 한도 초과"
            line_warnings.append("오늘 남은 모의주문 가능 횟수를 초과합니다.")

        if status == "주문 가능" and remaining_cash is not None and estimated_amount > remaining_cash:
            status = "현금 부족"
            line_warnings.append("예수금과 현금 버퍼를 반영하면 주문 가능 금액을 초과합니다.")

        if status == "주문 가능":
            executable_count += 1
            total_estimated_amount += estimated_amount
            if remaining_cash is not None:
                remaining_cash -= estimated_amount

        lines.append(
            KisOrderProposalLine(
                symbol=candidate.symbol,
                name=candidate.name,
                order_type=request.order_type,
                reference_price=reference_price,
                quantity=quantity,
                estimated_amount=estimated_amount,
                strategy_score=candidate.strategy_score,
                status=status,
                warnings=line_warnings,
                rationale=candidate.rationale[:2],
            )
        )

    if cash_verified and cash_budget is not None and total_estimated_amount > cash_budget:
        warnings.append("예상 주문금액이 현금 버퍼 반영 후 주문 가능 예수금을 초과합니다.")
    if any(line.status != "주문 가능" for line in lines):
        warnings.append("일부 종목은 금액, 현금, 주문 한도 조건 때문에 바로 주문할 수 없습니다.")

    return lines, total_estimated_amount, executable_count, warnings


def _allowed_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOWED_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://127.0.0.1:5173", "http://localhost:5173"]


app = FastAPI(
    title="QuantMate API",
    version="0.1.0",
    description="Local API for Korean equity screening, backtesting, and future KIS broker integration.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


STRATEGIES = [
    Strategy(
        code="relative-momentum-swing",
        name="상대 모멘텀 스윙",
        category="모멘텀",
        style="1주~3개월 스윙",
        holding_period="1주~3개월",
        summary=(
            "최근 3~12개월 동안 시장보다 강하게 오른 종목 중 거래대금과 추세 지속성이 함께 확인되는 후보를 찾습니다. "
            "강한 종목이 더 강해지는 구간에 유리하지만, 단기 급등 직후 추격 매수와 시장 급락장에서는 신호 신뢰도를 낮게 봅니다."
        ),
        rebalance_rule="주 1회 또는 월 1회 점검, 상위 후보 10~20개 교체",
        data_requirements=["일봉 OHLCV", "수정주가", "거래대금", "시장 대비 수익률"],
        universe_filter=["KOSPI/KOSDAQ 보통주", "거래정지/관리종목 제외", "거래대금 하위 종목 제외"],
        signal_rules=[
            "최근 3~12개월 수익률 상위",
            "최근 1개월 급등 과열 종목은 감점",
            "20일/60일 이동평균 위",
            "거래대금이 일정 수준 이상",
        ],
        ranking_rules=["상대수익률", "거래대금 증가", "추세 유지 점수", "과열 감점"],
        risk_controls=["급등 직후 추격 매수 감점", "시장 급락 구간 방어 규칙 필요", "거래량 급감 시 제외"],
        risk_notes=["횡보장과 급락장에서 성과가 나빠질 수 있음", "급등 직후 추격 매수 위험"],
        backtest_assumptions=["월 1회 리밸런싱", "상위 10개 동일 비중", "일봉 종가 기준 체결"],
        references=[
            "Jegadeesh & Titman (1993) 모멘텀 연구: https://www.jstor.org/stable/2328882",
            "Moskowitz, Ooi & Pedersen (2012) Time Series Momentum: https://ideas.repec.org/a/eee/jfinec/v104y2012i2p228-250.html",
        ],
    ),
    Strategy(
        code="value-quality-factor",
        name="가치/퀄리티 팩터",
        category="가치/퀄리티",
        style="수개월~1년 이상",
        holding_period="수개월~1년 이상",
        summary=(
            "PER/PBR 같은 가격 부담은 낮고 ROE, 현금흐름, 부채비율 같은 재무 품질은 일정 수준 이상인 종목을 찾습니다. "
            "단기 가격 흐름보다 기업의 체력과 저평가 해소 가능성을 보는 전략이라 재무 데이터 지연과 가치 함정 가능성을 함께 점검합니다."
        ),
        rebalance_rule="분기 또는 반기 점검, 재무 데이터 갱신 시 교체",
        data_requirements=["PER/PBR", "ROE", "부채비율", "영업이익률", "영업현금흐름"],
        universe_filter=["재무 데이터 결측 종목 제외", "적자 지속 종목 감점", "유동성 부족 종목 제외"],
        signal_rules=[
            "낮은 PER/PBR 또는 높은 이익수익률",
            "ROE와 영업현금흐름 양호",
            "부채비율 과도 종목 제외",
            "Piotroski F-Score식 재무 개선 신호 반영",
        ],
        ranking_rules=["밸류에이션 매력", "수익성", "재무 안정성", "재무 개선 점수"],
        risk_controls=["가치 함정 가능성 점검", "실적 악화 종목 제외", "재무 데이터 업데이트 지연 표시"],
        risk_notes=["가치 함정 가능성", "재무 데이터 업데이트 지연"],
        backtest_assumptions=["분기 리밸런싱", "상위 20개 동일 비중", "재무 발표 지연 반영"],
        references=[
            "Fama & French (2015) 5-factor model: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2287202",
            "Piotroski (2000) F-Score: https://www.jstor.org/stable/2672906",
        ],
    ),
    Strategy(
        code="growth-breakout-leader",
        name="성장 주도주 돌파형",
        category="성장/돌파",
        style="수주~수개월",
        holding_period="수주~수개월",
        summary=(
            "매출 또는 이익 성장이 뚜렷하고 가격이 신고가나 박스권 상단을 돌파하는 주도주 후보를 찾습니다. "
            "성장 기대와 수급이 동시에 붙는 구간을 노리지만, 고평가 성장주의 변동성과 돌파 실패 후 되돌림 위험을 크게 반영합니다."
        ),
        rebalance_rule="주 1회 점검, 돌파 실패나 이동평균 이탈 시 제외",
        data_requirements=["일봉 OHLCV", "52주 신고가", "거래량", "매출/이익 성장률", "섹터 강도"],
        universe_filter=["거래대금 하위 종목 제외", "극단적 고평가 종목 감점", "적자 성장주 별도 표시"],
        signal_rules=[
            "매출 또는 이익 성장률 양호",
            "52주 신고가 근접 또는 박스권 상단 돌파",
            "돌파일 거래량 증가",
            "시장/섹터 상대강도 양호",
        ],
        ranking_rules=["성장률", "신고가 근접도", "돌파 거래량", "섹터 상대강도"],
        risk_controls=["고평가 성장주 급락 위험 표시", "돌파 실패 시 제외", "약세장 신호 품질 저하 반영"],
        risk_notes=["고평가 성장주 급락 위험", "약세장에서 신호 품질 저하"],
        backtest_assumptions=["주 1회 리밸런싱", "돌파 실패 시 다음 점검일 제외", "상위 10개 동일 비중"],
        references=[
            "George & Hwang (2004) 52-week high momentum: https://www.jstor.org/stable/3694815",
            "International 52-week high momentum evidence: https://ideas.repec.org/a/eee/jimfin/v30y2011i1p180-204.html",
        ],
    ),
    Strategy(
        code="trend-breakout",
        name="추세 돌파형",
        category="추세/돌파",
        style="단기~중기 트레이딩",
        holding_period="며칠~수개월",
        summary=(
            "20일 또는 55일 고가 돌파처럼 명확한 가격 채널을 넘어서는 종목을 찾고 거래대금 증가로 신호를 확인합니다. "
            "빠른 추세 전환을 잡는 데 초점을 두므로 박스권 속임수 돌파, 갭 급등, 손절 기준 부재를 가장 큰 위험으로 봅니다."
        ),
        rebalance_rule="신호 발생 시 진입 후보 등록, 반대 신호나 손절 기준 도달 시 제외",
        data_requirements=["일봉 고가/저가/종가", "ATR", "거래대금", "이동평균"],
        universe_filter=["거래대금 부족 종목 제외", "변동성 과도 종목 감점", "갭 급등 종목 별도 표시"],
        signal_rules=[
            "20일 또는 55일 고가 돌파",
            "거래대금 증가",
            "ATR 기준 변동성 과도 종목 감점",
            "추세 이탈 또는 ATR 기반 손절 규칙 포함",
        ],
        ranking_rules=["돌파 강도", "거래대금 증가율", "ATR 대비 손익비", "추세 지속 점수"],
        risk_controls=["박스권 속임수 돌파 감점", "손절/청산 규칙 필수", "급등 갭 발생 시 진입 보류"],
        risk_notes=["박스권 장세에서 속임수 돌파가 많음", "손절/청산 규칙이 반드시 필요"],
        backtest_assumptions=["종가 돌파 기준 진입", "다음 거래일 시가 체결 가정", "ATR 기반 청산 비교"],
        references=[
            "Donchian channel breakout overview: https://www.investopedia.com/ask/answers/121714/how-are-donchian-channels-used-when-building-trading-strategies.asp",
            "Time-series momentum evidence: https://ideas.repec.org/a/eee/jfinec/v104y2012i2p228-250.html",
        ],
    ),
    Strategy(
        code="supply-demand-accumulation",
        name="수급 누적형",
        category="수급",
        style="며칠~수주 스윙",
        holding_period="며칠~수주",
        summary=(
            "외국인, 기관, 프로그램 매수세가 며칠 이상 누적되고 가격 추세가 함께 개선되는 종목을 찾습니다. "
            "큰 자금의 방향 전환을 따라가는 전략이지만, 수급 데이터 지연과 뉴스성 단기 매수세의 빠른 반전 가능성을 주의합니다."
        ),
        rebalance_rule="주 1회 점검, 수급 반전 또는 가격 추세 훼손 시 제외",
        data_requirements=["투자자별 순매수", "일봉 OHLCV", "거래대금", "이동평균"],
        universe_filter=["수급 데이터 결측 종목 제외", "거래대금 부족 종목 제외", "단기 뉴스 급등 종목 감점"],
        signal_rules=[
            "외국인 또는 기관 5~20일 순매수 누적",
            "거래대금 증가",
            "가격이 이동평균을 회복하거나 유지",
            "단기 급등 과열 종목 감점",
        ],
        ranking_rules=["외국인 순매수", "기관 순매수", "거래대금 증가", "가격 추세 회복"],
        risk_controls=["수급 데이터 지연 표시", "뉴스성 단기 수급 감점", "매수세 반전 시 제외"],
        risk_notes=["수급 데이터 지연과 정정 가능성", "뉴스성 단기 수급은 쉽게 반전될 수 있음"],
        backtest_assumptions=["주 1회 리밸런싱", "상위 10개 후보 관찰", "수급 데이터 제공 지연 반영"],
        references=[
            "Korea investor flow data will be mapped from KRX/KIS once connected",
            "Momentum evidence used as price-trend confirmation: https://www.jstor.org/stable/2328882",
        ],
    ),
    Strategy(
        code="low-volatility-defensive",
        name="저변동성/방어형",
        category="방어형",
        style="중기~장기",
        holding_period="수개월~1년 이상",
        summary=(
            "최근 변동성과 낙폭이 낮고 재무 안정성이 확인되는 종목을 찾아 포트폴리오의 방어 축으로 사용합니다. "
            "급등 수익보다 손실 폭을 낮추는 데 초점을 두며, 강한 상승장에서는 공격형 전략보다 뒤처질 수 있음을 전제로 합니다."
        ),
        rebalance_rule="월 1회 점검, 변동성 급등이나 재무 훼손 시 제외",
        data_requirements=["일봉 수익률 변동성", "MDD", "ROE", "부채비율", "거래대금"],
        universe_filter=["거래대금 부족 종목 제외", "재무 안정성 낮은 종목 제외", "저변동성 과열 종목 감점"],
        signal_rules=[
            "최근 6~12개월 변동성 낮음",
            "MDD 낮음",
            "재무 안정성 양호",
            "거래대금 부족 종목 제외",
        ],
        ranking_rules=["낮은 변동성", "낮은 MDD", "ROE 안정성", "밸류에이션 과열 감점"],
        risk_controls=["강한 상승장 소외 가능성 표시", "저변동성 과열 구간 감점", "유동성 부족 종목 제외"],
        risk_notes=["강한 상승장에서는 공격형 전략보다 뒤처질 수 있음", "저변동성이 비싸진 구간 주의"],
        backtest_assumptions=["월 1회 리밸런싱", "상위 20개 동일 비중", "변동성 급등 종목 제외"],
        references=[
            "Baker, Bradley & Wurgler (2011) Low-volatility anomaly: https://www.hbs.edu/faculty/Pages/item.aspx?num=39353",
            "Low-volatility anomaly paper: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1585031",
        ],
    ),
]

RECOMMENDATIONS = [
    Recommendation(
        symbol="005930",
        name="삼성전자",
        market="KOSPI",
        strategy_code="relative-momentum-swing",
        score=82,
        signal="관심",
        rationale=["시장 대표주로 유동성 우수", "단기 이동평균 회복", "거래대금 상위권"],
        risk_flags=["대형주는 급등 폭이 제한될 수 있음", "반도체 업황 뉴스 민감"],
    ),
    Recommendation(
        symbol="000660",
        name="SK하이닉스",
        market="KOSPI",
        strategy_code="growth-breakout-leader",
        score=78,
        signal="관찰",
        rationale=["섹터 모멘텀 양호", "실적 성장 기대 반영", "거래대금 상위권"],
        risk_flags=["반도체 업황 뉴스 민감"],
    ),
    Recommendation(
        symbol="012450",
        name="한화에어로스페이스",
        market="KOSPI",
        strategy_code="supply-demand-accumulation",
        score=76,
        signal="관심",
        rationale=["기관/외국인 동반 순매수 가정", "거래대금 증가", "가격 추세 양호"],
        risk_flags=["테마성 뉴스에 따른 변동성 확대 가능"],
    ),
    Recommendation(
        symbol="105560",
        name="KB금융",
        market="KOSPI",
        strategy_code="value-quality-factor",
        score=74,
        signal="관찰",
        rationale=["낮은 PBR", "ROE 안정성", "배당/자본정책 기대"],
        risk_flags=["금리와 경기 민감"],
    ),
]

BACKTEST = BacktestPreview(
    strategy_code="relative-momentum-swing",
    period="2023-01-02 ~ 2025-12-30 샘플",
    assumptions=[
        "선택 전략의 리밸런싱 규칙 사용",
        "거래 비용, 슬리피지, 보유 종목 수는 전략별 기본 파라미터 사용",
        "후보 종목은 전략 점수 상위 종목 기준",
        "현재 결과는 화면 검증용 샘플",
    ],
    metrics=[
        BacktestMetric(label="CAGR", value="18.4%", tone="positive"),
        BacktestMetric(label="MDD", value="-12.7%", tone="caution"),
        BacktestMetric(label="승률", value="57.8%", tone="neutral"),
        BacktestMetric(label="회전율", value="월 1.8회", tone="neutral"),
    ],
    equity_curve=[
        EquityPoint(day="2023-Q1", value=100.0),
        EquityPoint(day="2023-Q2", value=108.4),
        EquityPoint(day="2023-Q3", value=103.8),
        EquityPoint(day="2023-Q4", value=117.6),
        EquityPoint(day="2024-Q1", value=121.1),
        EquityPoint(day="2024-Q2", value=135.9),
        EquityPoint(day="2024-Q3", value=130.2),
        EquityPoint(day="2024-Q4", value=146.5),
        EquityPoint(day="2025-Q1", value=151.8),
        EquityPoint(day="2025-Q2", value=162.4),
        EquityPoint(day="2025-Q3", value=157.7),
        EquityPoint(day="2025-Q4", value=174.2),
    ],
)

BENCHMARKS: dict[str, dict[str, str]] = {
    "none": {"name": "비교 안 함", "symbol": "", "market": ""},
    "kospi200": {"name": "KOSPI 200", "symbol": "^KS200", "market": "KR"},
    "kosdaq": {"name": "KOSDAQ Composite", "symbol": "^KQ11", "market": "KR"},
    "sp500": {"name": "S&P 500", "symbol": "^GSPC", "market": "US"},
    "nasdaq100": {"name": "Nasdaq 100", "symbol": "^NDX", "market": "US"},
}
STRATEGY_PERFORMANCE_WINDOWS = (1, 3, 5, 10)
STRATEGY_PERFORMANCE_INITIAL_AMOUNT = 10_000_000
STRATEGY_PERFORMANCE_CACHE: dict[str, object] = {
    "key": None,
    "strategies": None,
}
KIS_QUOTE_SNAPSHOT_PROVIDER = "KIS Current Quote"
KIS_SUPPLY_FLOW_PROVIDER = "KIS Investor Flow"
KIS_SUPPLY_FLOW_COOLDOWN_UNTIL: datetime | None = None
KIS_RISK_INDICATOR_PROVIDER = "KIS Risk Indicator"
KIS_RISK_INDICATOR_COOLDOWN_UNTIL: datetime | None = None
KIS_FUNDAMENTAL_PROVIDER = "KIS Financial Ratio"
KIS_FUNDAMENTAL_COOLDOWN_UNTIL: datetime | None = None
OPEN_DART_FUNDAMENTAL_PROVIDER = "OpenDART Financial Statement"
OPEN_DART_FUNDAMENTAL_COOLDOWN_UNTIL: datetime | None = None
FUNDAMENTAL_PROVIDER_LABELS = {
    KIS_FUNDAMENTAL_PROVIDER: "KIS 재무",
    OPEN_DART_FUNDAMENTAL_PROVIDER: "OpenDART 재무",
}
DEFAULT_DAILY_PRICE_PROVIDER_PRIORITY = daily_price_provider_names()


def _daily_price_provider_priority() -> list[str]:
    configured = [
        item.strip()
        for item in os.getenv("DAILY_PRICE_PROVIDER_PRIORITY", "").split(",")
        if item.strip()
    ]
    supported = set(DEFAULT_DAILY_PRICE_PROVIDER_PRIORITY)
    priority = [provider for provider in configured if provider in supported]

    for provider in DEFAULT_DAILY_PRICE_PROVIDER_PRIORITY:
        if provider not in priority:
            priority.append(provider)

    return priority


def _find_system_strategy(strategy_code: str) -> Strategy | None:
    return next((item for item in STRATEGIES if item.code == strategy_code), None)


def _strategies_with_performance() -> list[Strategy]:
    cache_key = _strategy_performance_cache_key()
    cached_key = STRATEGY_PERFORMANCE_CACHE.get("key")
    cached_strategies = STRATEGY_PERFORMANCE_CACHE.get("strategies")
    if cached_key == cache_key and isinstance(cached_strategies, list):
        return cached_strategies

    enriched = [
        strategy.model_copy(
            update={"performance": _build_strategy_performance_snapshot(strategy)}
        )
        for strategy in STRATEGIES
    ]
    STRATEGY_PERFORMANCE_CACHE["key"] = cache_key
    STRATEGY_PERFORMANCE_CACHE["strategies"] = enriched
    return enriched


def _strategy_performance_cache_key() -> str:
    try:
        with SessionLocal() as session:
            latest_date = session.scalar(select(func.max(DailyPrice.trade_date)))
            row_count = session.scalar(select(func.count()).select_from(DailyPrice)) or 0
    except SQLAlchemyError:
        latest_date = None
        row_count = 0

    latest_label = latest_date.isoformat() if isinstance(latest_date, date) else "none"
    return f"{today_kst().isoformat()}:{latest_label}:{row_count}"


def _build_strategy_performance_snapshot(strategy: Strategy) -> StrategyPerformanceSnapshot:
    end_year = today_kst().year
    start_year = max(1990, end_year - max(STRATEGY_PERFORMANCE_WINDOWS) + 1)
    data_start_date = date(max(start_year - 1, 1990), 1, 1)
    end_date = _expected_latest_daily_price_date()
    symbols = [item["symbol"] for item in _seed_candidates_for_strategy(strategy.code, limit=50)]
    data_as_of = _latest_daily_price_date_for_symbols(symbols)
    windows = _empty_performance_windows(
        end_year=end_year,
        note="저장된 일봉 데이터가 부족해 백테스트 수익률을 계산하지 못했습니다.",
    )
    source = "daily-price-backtest:unavailable"
    note = "수익률은 예상치가 아니라 저장된 일봉 DB로 계산한 백테스트 결과입니다."

    try:
        result, provider = _build_daily_price_backtest_from_db(
            strategy_code=strategy.code,
            strategy_name=strategy.name,
            start_year=start_year,
            end_year=end_year,
            initial_amount=STRATEGY_PERFORMANCE_INITIAL_AMOUNT,
            candidate_symbols=symbols,
            start_date=data_start_date,
            end_date=end_date,
        )
    except SQLAlchemyError:
        result = None
        provider = ""

    if result is not None:
        source = f"daily-price-backtest:{provider}"
        windows = _performance_windows_from_backtest_result(
            result=result,
            end_year=end_year,
        )

    return StrategyPerformanceSnapshot(
        as_of=today_kst(),
        data_as_of=data_as_of,
        source=source,
        initial_amount=STRATEGY_PERFORMANCE_INITIAL_AMOUNT,
        windows=windows,
        update_policy="DB 일봉의 최신 거래일 또는 저장 건수가 바뀌면 한국시간 기준으로 다시 계산",
        note=note,
    )


def _empty_performance_windows(*, end_year: int, note: str) -> list[StrategyPerformanceWindow]:
    return [
        StrategyPerformanceWindow(
            label=f"최근 {years}년",
            years=years,
            start_year=max(1990, end_year - years + 1),
            end_year=end_year,
            status="unavailable",
            note=note,
        )
        for years in STRATEGY_PERFORMANCE_WINDOWS
    ]


def _performance_windows_from_backtest_result(
    *,
    result: dict[str, object],
    end_year: int,
) -> list[StrategyPerformanceWindow]:
    curve = _performance_curve_points(result.get("equity_curve", []))
    windows: list[StrategyPerformanceWindow] = []

    for years in STRATEGY_PERFORMANCE_WINDOWS:
        requested_start_year = max(1990, end_year - years + 1)
        if len(curve) < 2:
            windows.append(
                StrategyPerformanceWindow(
                    label=f"최근 {years}년",
                    years=years,
                    start_year=requested_start_year,
                    end_year=end_year,
                    status="unavailable",
                    note="해당 기간에 계산 가능한 백테스트 월별 자산 곡선이 없습니다.",
                )
            )
            continue

        last_point = curve[-1]
        target_months = years * 12
        target_start_index = last_point["month_index"] - target_months
        start_point = next(
            (point for point in curve if point["month_index"] >= target_start_index),
            curve[0],
        )
        window_curve = [point for point in curve if point["month_index"] >= start_point["month_index"]]
        elapsed_months = last_point["month_index"] - start_point["month_index"]
        start_balance = start_point["portfolio"]
        final_amount = last_point["portfolio"]

        if elapsed_months <= 0 or start_balance <= 0:
            windows.append(
                StrategyPerformanceWindow(
                    label=f"최근 {years}년",
                    years=years,
                    start_year=requested_start_year,
                    end_year=end_year,
                    status="unavailable",
                    note="연간 수익률 행의 금액 정보를 해석하지 못했습니다.",
                )
            )
            continue

        total_return = (final_amount / start_balance - 1) * 100
        cagr = (math.pow(final_amount / start_balance, 12 / elapsed_months) - 1) * 100
        mdd = _performance_window_mdd(window_curve)
        status = "complete" if elapsed_months >= target_months else "partial"
        note = (
            "요청한 기간 전체를 계산했습니다."
            if status == "complete"
            else f"{years}년 중 DB로 계산 가능한 {elapsed_months}개월만 반영했습니다."
        )
        windows.append(
            StrategyPerformanceWindow(
                label=f"최근 {years}년",
                years=years,
                start_year=start_point["year"],
                end_year=last_point["year"],
                cagr=round(cagr, 1),
                total_return=round(total_return, 1),
                mdd=round(mdd, 1),
                final_amount=final_amount,
                status=status,
                note=note,
            )
        )

    return windows


def _performance_window_mdd(curve: list[dict[str, int]]) -> float:
    peak = 0
    max_drawdown = 0.0
    for point in curve:
        value = point["portfolio"]
        if value <= 0:
            continue
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = min(max_drawdown, (value / peak - 1) * 100)
    return max_drawdown


def _performance_curve_points(value: object) -> list[dict[str, int]]:
    if not isinstance(value, list):
        return []

    points: list[dict[str, int]] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        month_index = _performance_month_index(row.get("label"))
        portfolio = _optional_int(row.get("portfolio"))
        if month_index is None or portfolio is None or portfolio <= 0:
            continue
        points.append(
            {
                "month_index": month_index,
                "year": month_index // 12,
                "portfolio": portfolio,
            }
        )

    return sorted(points, key=lambda item: item["month_index"])


def _performance_month_index(value: object) -> int | None:
    if not isinstance(value, str) or len(value) < 7:
        return None
    try:
        year_text, month_text = value.replace("-", ".").split(".")[:2]
        year = int(year_text)
        month = int(month_text)
    except ValueError:
        return None
    if month < 1 or month > 12:
        return None
    return year * 12 + month - 1


def _latest_daily_price_date_for_symbols(symbols: list[str]) -> date | None:
    if not symbols:
        return None
    try:
        with SessionLocal() as session:
            return session.scalar(
                select(func.max(DailyPrice.trade_date))
                .join(Instrument, DailyPrice.instrument_id == Instrument.id)
                .where(Instrument.symbol.in_(symbols))
            )
    except SQLAlchemyError:
        return None


def _user_strategy_response(strategy: UserStrategy) -> UserStrategyResponse:
    return UserStrategyResponse(
        id=strategy.id,
        code=strategy.code,
        name=strategy.name,
        summary=strategy.summary,
        formula=strategy.formula,
        result_count=strategy.result_count,
        created_at=strategy.created_at,
    )


def _normalize_user_strategy_create(request: UserStrategyCreate) -> UserStrategyCreate:
    name = request.name.strip()
    summary = request.summary.strip()
    formula = request.formula.strip()

    if not name:
        raise HTTPException(status_code=422, detail="전략명을 입력하세요.")
    if not summary:
        raise HTTPException(status_code=422, detail="전략 소개를 입력하세요.")
    if not formula:
        raise HTTPException(status_code=422, detail="전략 조건식이 비어 있습니다.")

    return UserStrategyCreate(
        name=name,
        summary=summary,
        formula=formula,
        result_count=request.result_count,
    )


def _load_active_user_strategy(strategy_code: str) -> UserStrategy | None:
    try:
        with SessionLocal() as session:
            return session.scalar(
                select(UserStrategy).where(
                    UserStrategy.code == strategy_code,
                    UserStrategy.is_active.is_(True),
                )
            )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"사용자 전략 DB 연결 확인 필요: {exc.__class__.__name__}",
        ) from exc


def _save_backtest_run(
    *,
    result: dict[str, object],
    request: BacktestRunRequest,
) -> int | None:
    first_year = min(request.start_year, request.end_year)
    last_year = max(request.start_year, request.end_year)

    try:
        with SessionLocal() as session:
            run = BacktestRun(
                strategy_code=str(result["strategy_code"]),
                strategy_name=str(result["strategy_name"]),
                source=str(result["source"]),
                start_year=first_year,
                end_year=last_year,
                initial_amount=int(result["initial_amount"]),
                final_amount=int(result["final_amount"]),
                result_json=json.dumps(result, ensure_ascii=False),
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run.id
    except SQLAlchemyError:
        return None


def _backtest_summary(run: BacktestRun) -> BacktestRunSummary:
    return BacktestRunSummary(
        id=run.id,
        strategy_code=run.strategy_code,
        strategy_name=run.strategy_name,
        period=f"{run.start_year} ~ {run.end_year}",
        source=run.source,
        initial_amount=run.initial_amount,
        final_amount=run.final_amount,
        created_at=run.created_at,
    )


def _saved_backtest_response(run: BacktestRun) -> BacktestRunResponse:
    try:
        payload = json.loads(run.result_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="저장된 백테스트 결과를 해석하지 못했습니다.") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="저장된 백테스트 결과 형식이 올바르지 않습니다.")

    payload["run_id"] = run.id
    payload.setdefault("strategy_code", run.strategy_code)
    payload.setdefault("strategy_name", run.strategy_name)
    payload.setdefault("source", run.source)
    payload.setdefault("period", f"{run.start_year} ~ {run.end_year}")
    payload.setdefault("initial_amount", run.initial_amount)
    payload.setdefault("final_amount", run.final_amount)
    payload.setdefault("benchmark_code", "none")
    payload.setdefault("benchmark_name", "")
    payload.setdefault("benchmark_curve", [])
    payload.setdefault(
        "backtest_policy",
        backtest_policy_for_strategy(run.strategy_code, initial_amount=run.initial_amount),
    )
    _attach_saved_benchmark_curve_if_missing(payload=payload, run=run)

    return BacktestRunResponse(**payload)


def _attach_saved_benchmark_curve_if_missing(
    *,
    payload: dict[str, object],
    run: BacktestRun,
) -> None:
    benchmark_code = str(payload.get("benchmark_code") or "none").strip().lower()
    payload["benchmark_code"] = benchmark_code

    if benchmark_code == "none" or benchmark_code not in BENCHMARKS:
        payload["benchmark_name"] = ""
        payload["benchmark_curve"] = []
        return

    payload["benchmark_name"] = BENCHMARKS[benchmark_code]["name"]

    existing_curve = payload.get("benchmark_curve")
    if isinstance(existing_curve, list) and existing_curve:
        return

    backtest_policy = payload.get("backtest_policy")
    policy_rebalance_interval = None
    policy_holding_count = None
    if isinstance(backtest_policy, dict):
        policy_rebalance_interval = _optional_int(backtest_policy.get("rebalance_interval_months"))
        policy_holding_count = _optional_int(backtest_policy.get("holding_count"))

    _attach_benchmark_curve(
        result=payload,
        request=BacktestRunRequest(
            strategy_code=run.strategy_code,
            start_year=run.start_year,
            end_year=run.end_year,
            initial_amount=int(payload.get("initial_amount") or run.initial_amount),
            benchmark_code=benchmark_code,
            rebalance_interval_months=policy_rebalance_interval,
            holding_count=policy_holding_count,
        ),
    )


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _attach_benchmark_curve(
    *,
    result: dict[str, object],
    request: BacktestRunRequest,
) -> None:
    benchmark_code = request.benchmark_code.strip().lower()
    benchmark = BENCHMARKS.get(benchmark_code)

    if benchmark is None:
        supported = ", ".join(BENCHMARKS)
        raise HTTPException(status_code=400, detail=f"지원하지 않는 비교군입니다. 사용 가능: {supported}")

    result["benchmark_code"] = benchmark_code
    result["benchmark_name"] = benchmark["name"] if benchmark_code != "none" else ""
    result["benchmark_curve"] = []

    if benchmark_code == "none":
        return

    first_year = min(request.start_year, request.end_year)
    last_year = max(request.start_year, request.end_year)

    try:
        prices = fetch_yfinance_symbol_daily_prices(
            yahoo_symbol=benchmark["symbol"],
            start=date(first_year, 1, 1),
            end=date(last_year, 12, 31),
        )
    except (MarketDataProviderUnavailable, ValueError):
        return

    result["benchmark_curve"] = _build_benchmark_curve(
        prices=prices,
        initial_amount=request.initial_amount,
    )


def _backtest_parameter_overrides_from_request(
    request: BacktestRunRequest,
) -> dict[str, int]:
    overrides: dict[str, int] = {}
    if request.rebalance_interval_months is not None:
        overrides["rebalance_interval_months"] = request.rebalance_interval_months
    if request.holding_count is not None:
        overrides["holding_count"] = request.holding_count
    return overrides


def _build_benchmark_curve(
    *,
    prices: list[dict[str, object]],
    initial_amount: int,
) -> list[dict[str, object]]:
    monthly_prices: dict[str, list[dict[str, object]]] = {}

    for row in prices:
        trade_date = _row_trade_date(row)
        month_key = f"{trade_date.year}-{trade_date.month:02d}"
        monthly_prices.setdefault(month_key, []).append(row)

    ordered_months = sorted(monthly_prices)
    if len(ordered_months) < 2:
        return []

    curve: list[dict[str, object]] = []
    first_rows = sorted(monthly_prices[ordered_months[0]], key=_row_trade_date)
    base_price = _decimal_or_none(first_rows[0].get("close")) if first_rows else None
    if base_price is None or base_price <= 0:
        return []

    for month_index, month_key in enumerate(ordered_months):
        rows = sorted(monthly_prices[month_key], key=_row_trade_date)
        end_price = _decimal_or_none(rows[-1].get("close"))

        if end_price is None or end_price <= 0:
            continue

        benchmark_value = initial_amount if month_index == 0 else round(float(initial_amount) * float(end_price / base_price))
        curve.append({"label": month_key.replace("-", "."), "benchmark": benchmark_value})

    return curve


def _build_daily_price_backtest_if_available(
    *,
    strategy_code: str,
    strategy_name: str,
    start_year: int,
    end_year: int,
    initial_amount: int,
    candidate_formula: str | None = None,
    backtest_parameters: dict[str, int] | None = None,
) -> dict[str, object] | None:
    first_year = min(start_year, end_year)
    last_year = max(start_year, end_year)
    data_start_date = date(max(first_year - 1, 1990), 1, 1)
    end_date = date(last_year, 12, 31)
    candidate_symbols = [item["symbol"] for item in _seed_candidates_for_strategy(strategy_code, limit=50)]

    existing_result, _existing_provider = _build_daily_price_backtest_from_db(
        strategy_code=strategy_code,
        strategy_name=strategy_name,
        start_year=start_year,
        end_year=end_year,
        initial_amount=initial_amount,
        candidate_symbols=candidate_symbols,
        start_date=data_start_date,
        end_date=end_date,
        candidate_formula=candidate_formula,
        backtest_parameters=backtest_parameters,
    )
    if existing_result is not None and _backtest_result_covers_requested_start(
        result=existing_result,
        first_year=first_year,
    ):
        return existing_result

    _auto_import_kis_daily_prices_for_backtest(
        strategy_code=strategy_code,
        start_date=data_start_date,
        end_date=end_date,
    )

    kis_result, _kis_provider = _build_daily_price_backtest_from_db(
        strategy_code=strategy_code,
        strategy_name=strategy_name,
        start_year=start_year,
        end_year=end_year,
        initial_amount=initial_amount,
        candidate_symbols=candidate_symbols,
        start_date=data_start_date,
        end_date=end_date,
        candidate_formula=candidate_formula,
        backtest_parameters=backtest_parameters,
    )
    if kis_result is not None and _backtest_result_covers_requested_start(
        result=kis_result,
        first_year=first_year,
    ):
        return kis_result

    _auto_import_yahoo_daily_prices_for_backtest(
        strategy_code=strategy_code,
        start_date=data_start_date,
        end_date=end_date,
    )

    refreshed_result, _provider = _build_daily_price_backtest_from_db(
        strategy_code=strategy_code,
        strategy_name=strategy_name,
        start_year=start_year,
        end_year=end_year,
        initial_amount=initial_amount,
        candidate_symbols=candidate_symbols,
        start_date=data_start_date,
        end_date=end_date,
        candidate_formula=candidate_formula,
        backtest_parameters=backtest_parameters,
    )
    return refreshed_result or kis_result or existing_result


def _backtest_result_covers_requested_start(*, result: dict[str, object], first_year: int) -> bool:
    rebalance_history = result.get("rebalance_history")
    if not isinstance(rebalance_history, list) or not rebalance_history:
        return False

    first_row = rebalance_history[0]
    if not isinstance(first_row, dict):
        return False

    first_rebalance_month = str(first_row.get("date") or "").replace(".", "-")
    return first_rebalance_month <= f"{first_year}-01"


def _build_daily_price_backtest_from_db(
    *,
    strategy_code: str,
    strategy_name: str,
    start_year: int,
    end_year: int,
    initial_amount: int,
    candidate_symbols: list[str],
    start_date: date,
    end_date: date,
    candidate_formula: str | None = None,
    backtest_parameters: dict[str, int] | None = None,
) -> tuple[dict[str, object] | None, str]:
    if not candidate_symbols:
        return None, ""

    try:
        with SessionLocal() as session:
            price_rows, provider = _load_backtest_price_rows(
                session=session,
                symbols=candidate_symbols,
                start_date=start_date,
                end_date=end_date,
            )
    except SQLAlchemyError:
        return None, ""

    if not price_rows:
        return None, ""

    result = build_daily_price_backtest(
        strategy_code=strategy_code,
        strategy_name=strategy_name,
        start_year=start_year,
        end_year=end_year,
        initial_amount=initial_amount,
        price_rows=price_rows,
        provider=provider,
        candidate_formula=candidate_formula,
        backtest_parameters=backtest_parameters,
    )
    return result, provider if result is not None else ""


def _seed_candidates_for_strategy(strategy_code: str, limit: int) -> list[dict[str, object]]:
    seen_symbols: set[str] = set()
    candidates: list[dict[str, object]] = []

    for candidate in build_strategy_candidates(strategy_code, limit=min(limit, 30)):
        symbol = str(candidate["symbol"])
        if symbol in seen_symbols:
            continue
        candidates.append(candidate)
        seen_symbols.add(symbol)

    if is_kis_open_api_ready() and len(candidates) < limit:
        try:
            ranking_rows = fetch_kis_market_cap_ranking(limit=limit)
            _refresh_instrument_names_from_market_cap_ranking(ranking_rows)
            for row in ranking_rows:
                symbol = str(row["symbol"])
                if symbol in seen_symbols:
                    continue
                exchange = _normalize_exchange(str(row.get("exchange") or "KOSPI"))
                candidates.append(
                    {
                        "symbol": symbol,
                        "name": str(row["name"]),
                        "exchange": exchange,
                        "sector": "미분류",
                        "industry": "미분류",
                        "market_cap": _market_cap_to_trillion(row.get("market_cap")),
                        "price": int(row.get("price") or 0),
                        "change_pct": float(row.get("change_rate") or 0),
                        "per": 0,
                        "pbr": 0,
                        "roe": 0,
                        "revenue_growth": 0,
                        "foreign_net_buy_5d": 0,
                        "institution_net_buy_5d": 0,
                        "supply_score": 50,
                        "short_sale_ratio": 0,
                        "momentum": 50,
                    }
                )
                seen_symbols.add(symbol)
                if len(candidates) >= limit:
                    break
        except MarketDataProviderUnavailable:
            pass

    if len(candidates) < limit:
        for candidate in _stored_price_seed_candidates(limit=limit * 2):
            symbol = str(candidate["symbol"])
            if symbol in seen_symbols:
                continue
            candidates.append(candidate)
            seen_symbols.add(symbol)
            if len(candidates) >= limit:
                break

    return candidates[:limit]


def _refresh_instrument_names_from_market_cap_ranking(rows: list[dict[str, object]]) -> None:
    if not rows:
        return

    try:
        with SessionLocal() as session:
            market = _get_or_create_kr_market(session)
            updated = False

            for row in rows:
                symbol = str(row.get("symbol") or "").strip().upper()
                name = str(row.get("name") or "").strip()
                if not symbol or not name or name == symbol:
                    continue

                instrument = _get_or_create_instrument(
                    session=session,
                    market=market,
                    symbol=symbol,
                    name=name,
                    exchange=_normalize_exchange(str(row.get("exchange") or "KOSPI")),
                )
                if instrument.name != name:
                    instrument.name = name
                updated = True

            if updated:
                session.commit()
    except SQLAlchemyError:
        return


def _normalize_exchange(exchange: str) -> str:
    normalized = exchange.strip().upper()
    if normalized in {"KOSPI", "KOSDAQ", "KONEX"}:
        return normalized
    if normalized in {"KR", "ALL", "KOSPI200"}:
        return "KOSPI"
    return normalized or "KOSPI"


def _stored_price_seed_candidates(limit: int) -> list[dict[str, object]]:
    safe_limit = max(1, min(limit, 200))
    provider_priority = _daily_price_provider_priority()
    latest_price_dates = (
        select(
            DailyPrice.instrument_id.label("instrument_id"),
            func.max(DailyPrice.trade_date).label("latest_trade_date"),
        )
        .where(
            DailyPrice.provider.in_(provider_priority),
            DailyPrice.is_adjusted.is_(False),
        )
        .group_by(DailyPrice.instrument_id)
        .subquery()
    )

    try:
        with SessionLocal() as session:
            rows = session.execute(
                select(
                    Instrument.symbol,
                    Instrument.name,
                    Instrument.exchange,
                    DailyPrice.close_price,
                    func.coalesce(
                        DailyPrice.trading_value,
                        DailyPrice.close_price * DailyPrice.volume,
                        0,
                    ).label("estimated_trading_value"),
                )
                .join(latest_price_dates, latest_price_dates.c.instrument_id == Instrument.id)
                .join(
                    DailyPrice,
                    (DailyPrice.instrument_id == latest_price_dates.c.instrument_id)
                    & (DailyPrice.trade_date == latest_price_dates.c.latest_trade_date)
                    & (DailyPrice.is_adjusted.is_(False)),
                )
                .where(DailyPrice.provider.in_(provider_priority))
                .order_by(func.coalesce(DailyPrice.trading_value, DailyPrice.close_price * DailyPrice.volume, 0).desc())
                .limit(safe_limit)
            ).all()
    except SQLAlchemyError:
        return []

    candidates: list[dict[str, object]] = []
    seen_symbols: set[str] = set()
    for row in rows:
        symbol = str(row.symbol)
        if symbol in seen_symbols:
            continue

        candidates.append(
            {
                "symbol": symbol,
                "name": str(row.name or symbol),
                "exchange": str(row.exchange or "KOSPI"),
                "sector": "미분류",
                "industry": "미분류",
                "market_cap": 0,
                "price": int(_decimal_or_none(row.close_price) or 0),
                "change_pct": 0,
                "per": 0,
                "pbr": 0,
                "roe": 0,
                "revenue_growth": 0,
                "foreign_net_buy_5d": 0,
                "institution_net_buy_5d": 0,
                "supply_score": 50,
                "short_sale_ratio": 0,
                "momentum": 50,
            }
        )
        seen_symbols.add(symbol)

    return candidates


def _market_cap_to_trillion(value: object) -> float:
    parsed = _decimal_or_none(value)
    if parsed is None:
        return 0.0
    return round(float(parsed) / 10_000, 2)


def _auto_import_kis_daily_prices_for_backtest(
    *,
    strategy_code: str,
    start_date: date,
    end_date: date,
) -> KisDailyPriceBatchImportResponse | None:
    if not is_kis_open_api_ready():
        return None

    try:
        return _import_kis_daily_prices_for_strategy_candidates(
            KisDailyPriceBatchImportRequest(
                strategy_code=strategy_code,
                start=start_date,
                end=end_date,
                max_symbols=10,
                is_adjusted=False,
            )
        )
    except (HTTPException, SQLAlchemyError, ValueError, MarketDataProviderUnavailable):
        return None


def _auto_import_yahoo_daily_prices_for_backtest(
    *,
    strategy_code: str,
    start_date: date,
    end_date: date,
) -> YahooDailyPriceBatchImportResponse | None:
    try:
        return _import_yahoo_daily_prices_for_strategy_candidates(
            YahooDailyPriceBatchImportRequest(
                strategy_code=strategy_code,
                start=start_date,
                end=end_date,
                max_symbols=30,
                is_adjusted=False,
            )
        )
    except (HTTPException, SQLAlchemyError, ValueError):
        return None


def _load_backtest_price_rows(
    *,
    session,
    symbols: list[str],
    start_date: date,
    end_date: date,
) -> tuple[list[dict[str, object]], str]:
    provider_priority = _daily_price_provider_priority()
    rows = session.execute(
        select(
            Instrument.symbol,
            Instrument.name,
            DailyPrice.trade_date,
            DailyPrice.close_price,
            DailyPrice.provider,
        )
        .join(Instrument, Instrument.id == DailyPrice.instrument_id)
        .where(
            Instrument.symbol.in_(symbols),
            DailyPrice.trade_date >= start_date,
            DailyPrice.trade_date <= end_date,
            DailyPrice.is_adjusted.is_(False),
            DailyPrice.provider.in_(provider_priority),
        )
        .order_by(Instrument.symbol, DailyPrice.provider, DailyPrice.trade_date)
    ).all()

    grouped_by_provider: dict[str, list[dict[str, object]]] = {provider: [] for provider in provider_priority}
    for row in rows:
        grouped_by_provider[row.provider].append(
            {
                "symbol": row.symbol,
                "name": row.name,
                "trade_date": row.trade_date,
                "close_price": row.close_price,
                "provider": row.provider,
            }
        )

    minimum_symbols = min(10, len(symbols))
    provider_options: list[tuple[list[dict[str, object]], str]] = []
    for provider in provider_priority:
        provider_rows = _filter_backtest_price_rows_for_coverage(grouped_by_provider[provider])
        if _has_minimum_price_coverage(provider_rows, minimum_symbols=1):
            provider_options.append((provider_rows, provider))

    mixed_rows, mixed_provider = _build_mixed_backtest_price_rows(
        grouped_by_provider=grouped_by_provider,
        provider_priority=provider_priority,
        start_date=start_date,
        end_date=end_date,
    )
    if _has_minimum_price_coverage(mixed_rows, minimum_symbols=1):
        provider_options.append((mixed_rows, mixed_provider))

    enough_symbol_options = [
        (rows, provider)
        for rows, provider in provider_options
        if _has_minimum_price_coverage(rows, minimum_symbols=minimum_symbols)
    ]
    if enough_symbol_options:
        return _best_backtest_price_rows_for_period(
            options=enough_symbol_options,
            provider_priority=provider_priority,
            start_date=start_date,
            end_date=end_date,
        )

    if provider_options:
        return _best_backtest_price_rows_for_period(
            options=provider_options,
            provider_priority=provider_priority,
            start_date=start_date,
            end_date=end_date,
        )

    return [], ""


def _filter_backtest_price_rows_for_coverage(
    price_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows_by_symbol: dict[str, list[dict[str, object]]] = {}
    for row in price_rows:
        rows_by_symbol.setdefault(str(row["symbol"]), []).append(row)

    covered_rows: list[dict[str, object]] = []
    for rows in rows_by_symbol.values():
        months = {
            f"{_row_trade_date(row).year}-{_row_trade_date(row).month:02d}"
            for row in rows
        }
        if len(months) >= 2 and len(rows) >= 4:
            covered_rows.extend(rows)

    return covered_rows


def _has_minimum_price_coverage(
    price_rows: list[dict[str, object]],
    *,
    minimum_symbols: int = 1,
) -> bool:
    symbols = {str(row["symbol"]) for row in price_rows}
    months = {
        f"{_row_trade_date(row).year}-{_row_trade_date(row).month:02d}"
        for row in price_rows
    }
    return len(symbols) >= minimum_symbols and len(months) >= 2 and len(price_rows) >= minimum_symbols * 4


def _best_backtest_price_rows_for_period(
    *,
    options: list[tuple[list[dict[str, object]], str]],
    provider_priority: list[str],
    start_date: date,
    end_date: date,
) -> tuple[list[dict[str, object]], str]:
    return max(
        options,
        key=lambda item: _backtest_price_coverage_score(
            price_rows=item[0],
            provider=item[1],
            provider_priority=provider_priority,
            start_date=start_date,
            end_date=end_date,
        ),
    )


def _backtest_price_coverage_score(
    *,
    price_rows: list[dict[str, object]],
    provider: str,
    provider_priority: list[str],
    start_date: date,
    end_date: date,
) -> tuple[int, int, int, int, int, int]:
    if not price_rows:
        return (0, 0, 0, 0, 0, 0)

    effective_end_date = min(end_date, today_kst())
    start_month_index = _month_index_from_date(start_date)
    end_month_index = _month_index_from_date(effective_end_date)
    expected_months = max(1, end_month_index - start_month_index + 1)
    provider_rank = provider_priority.index(provider) if provider in provider_priority else len(provider_priority)

    rows_by_symbol: dict[str, list[dict[str, object]]] = {}
    covered_months: set[int] = set()
    for row in price_rows:
        trade_date = _row_trade_date(row)
        month_index = _month_index_from_date(trade_date)
        covered_months.add(month_index)
        rows_by_symbol.setdefault(str(row["symbol"]), []).append(row)

    full_period_symbol_count = 0
    for rows in rows_by_symbol.values():
        symbol_months = {_month_index_from_date(_row_trade_date(row)) for row in rows}
        if not symbol_months:
            continue
        if min(symbol_months) <= start_month_index and max(symbol_months) >= end_month_index:
            full_period_symbol_count += 1

    bounded_month_count = len(
        {
            month_index
            for month_index in covered_months
            if start_month_index <= month_index <= end_month_index
        }
    )
    covers_start_month = int(start_month_index in covered_months)
    covers_end_month = int(end_month_index in covered_months)

    return (
        min(full_period_symbol_count, len(rows_by_symbol)),
        min(bounded_month_count, expected_months),
        covers_start_month,
        covers_end_month,
        len(rows_by_symbol),
        -provider_rank,
    )


def _month_index_from_date(value: date) -> int:
    return value.year * 12 + value.month - 1


def _build_mixed_backtest_price_rows(
    *,
    grouped_by_provider: dict[str, list[dict[str, object]]],
    provider_priority: list[str],
    start_date: date,
    end_date: date,
) -> tuple[list[dict[str, object]], str]:
    rows_by_symbol_provider: dict[str, dict[str, list[dict[str, object]]]] = {}

    for provider, rows in grouped_by_provider.items():
        for row in rows:
            symbol = str(row["symbol"])
            rows_by_symbol_provider.setdefault(symbol, {}).setdefault(provider, []).append(row)

    mixed_rows: list[dict[str, object]] = []
    used_providers: list[str] = []

    for provider_rows in rows_by_symbol_provider.values():
        symbol_options: list[tuple[list[dict[str, object]], str]] = []
        for provider in provider_priority:
            covered_rows = _filter_backtest_price_rows_for_coverage(provider_rows.get(provider, []))
            if _has_minimum_price_coverage(covered_rows, minimum_symbols=1):
                symbol_options.append((covered_rows, provider))

        if not symbol_options:
            continue

        best_rows, best_provider = _best_backtest_price_rows_for_period(
            options=symbol_options,
            provider_priority=provider_priority,
            start_date=start_date,
            end_date=end_date,
        )
        mixed_rows.extend(best_rows)
        if best_provider not in used_providers:
            used_providers.append(best_provider)

    return mixed_rows, _mixed_provider_label(used_providers)


def _build_daily_price_strategy_candidates_if_available(
    strategy_code: str,
    *,
    limit: int = 12,
) -> tuple[str, list[dict[str, object]]] | None:
    safe_limit = max(1, min(limit, 100))
    scoring_pool_limit = min(max(safe_limit * 3, 30), 100)
    symbols = [str(item["symbol"]) for item in _seed_candidates_for_strategy(strategy_code, limit=max(safe_limit, 50))]
    if not symbols:
        return None

    try:
        with SessionLocal() as session:
            price_rows, provider = _load_strategy_candidate_price_rows(
                session=session,
                symbols=symbols,
                start_date=_candidate_price_start_date(),
                end_date=today_kst(),
            )
            quote_snapshots = _load_latest_quote_snapshots_by_symbol(session=session, symbols=symbols)
            fundamentals = _load_fundamental_metrics_by_symbol(session=session, symbols=symbols)
            supply_flows = _load_supply_flow_metrics_by_symbol(session=session, symbols=symbols)
            risk_indicators = _load_risk_indicator_metrics_by_symbol(session=session, symbols=symbols)
    except SQLAlchemyError:
        return None

    if not price_rows:
        return None

    candidates = build_strategy_candidates_from_daily_prices(
        strategy_code=strategy_code,
        price_rows=price_rows,
        limit=scoring_pool_limit,
    )
    if not candidates:
        return None

    if quote_snapshots:
        candidates = enrich_strategy_candidates_with_quote_snapshots(
            candidates=candidates,
            quote_snapshots=quote_snapshots,
        )
        provider = f"{provider} + KIS 현재가"

    if fundamentals:
        candidates = enrich_strategy_candidates_with_fundamentals(
            strategy_code=strategy_code,
            candidates=candidates,
            fundamentals=fundamentals,
        )
        provider = f"{provider} + {_fundamental_provider_source_label(fundamentals)}"

    if supply_flows:
        candidates = enrich_strategy_candidates_with_supply_flows(
            candidates=candidates,
            supply_flows=supply_flows,
        )
        provider = f"{provider} + KIS 수급"

    if risk_indicators:
        candidates = enrich_strategy_candidates_with_risk_indicators(
            candidates=candidates,
            risk_indicators=risk_indicators,
        )
        provider = f"{provider} + KIS 리스크"

    candidates = refresh_candidate_scores(strategy_code=strategy_code, candidates=candidates)
    candidates = apply_candidate_quality_filters(strategy_code, candidates, limit=safe_limit)

    return f"daily-price-candidates:{provider}", candidates


def _fundamental_provider_source_label(fundamentals: dict[str, dict[str, object]]) -> str:
    labels: list[str] = []
    for metrics in fundamentals.values():
        provider_label = str(metrics.get("provider_label") or "").strip()
        if not provider_label:
            continue
        for label in provider_label.split(" + "):
            if label and label not in labels:
                labels.append(label)

    return " + ".join(labels) if labels else "재무"


def _auto_import_yahoo_daily_prices_for_strategy_candidates_if_needed(
    strategy_code: str,
    *,
    max_symbols: int = 30,
) -> None:
    try:
        _import_yahoo_daily_prices_for_strategy_candidates(
            YahooDailyPriceBatchImportRequest(
                strategy_code=strategy_code,
                start=_candidate_price_start_date(),
                end=today_kst(),
                max_symbols=max(1, min(max_symbols, 30)),
                is_adjusted=False,
            )
        )
    except (HTTPException, SQLAlchemyError, ValueError):
        return


def _auto_import_kis_daily_prices_for_strategy_candidates_if_needed(
    strategy_code: str,
    *,
    max_symbols: int = 10,
) -> bool:
    if not is_kis_open_api_ready():
        return False

    try:
        response = _import_kis_daily_prices_for_strategy_candidates(
            KisDailyPriceBatchImportRequest(
                strategy_code=strategy_code,
                start=_candidate_price_start_date(),
                end=today_kst(),
                max_symbols=max(1, min(max_symbols, 10)),
                is_adjusted=False,
            )
        )
        return response.success_count > 0
    except (HTTPException, SQLAlchemyError, ValueError, MarketDataProviderUnavailable):
        return False


def _auto_import_kis_quote_snapshots_for_strategy_candidates_if_needed(
    strategy_code: str,
    *,
    max_symbols: int = 12,
) -> None:
    candidates = _seed_candidates_for_strategy(strategy_code, limit=max_symbols)
    _auto_import_kis_quote_snapshots_for_candidates_if_needed(
        candidates=candidates,
        max_symbols=max_symbols,
    )


def _auto_import_kis_quote_snapshots_for_candidates_if_needed(
    *,
    candidates: list[dict[str, object]],
    max_symbols: int = 12,
) -> None:
    if not is_kis_open_api_ready():
        return

    safe_limit = max(1, min(max_symbols, _kis_current_quote_refresh_max_symbols()))
    target_candidates = candidates[:safe_limit]
    symbols = [str(item["symbol"]) for item in target_candidates]
    if not symbols:
        return

    try:
        max_age_minutes = _kis_current_quote_max_age_minutes()
        existing_symbols: set[str] = set()
        if max_age_minutes > 0:
            fresh_after = now_kst_naive() - timedelta(minutes=max_age_minutes)
            with SessionLocal() as session:
                existing_symbols = set(
                    session.scalars(
                        select(Instrument.symbol)
                        .join(QuoteSnapshot, QuoteSnapshot.instrument_id == Instrument.id)
                        .where(
                            Instrument.symbol.in_(symbols),
                            QuoteSnapshot.provider == KIS_QUOTE_SNAPSHOT_PROVIDER,
                            QuoteSnapshot.snapshot_date == today_kst(),
                            QuoteSnapshot.created_at >= fresh_after,
                        )
                    ).all()
                )
    except SQLAlchemyError:
        return

    missing_symbols = [symbol for symbol in symbols if symbol not in existing_symbols]
    if not missing_symbols:
        return

    for candidate in target_candidates:
        symbol = str(candidate["symbol"])
        if symbol not in missing_symbols:
            continue

        try:
            quote = fetch_kis_current_price(symbol)
            with SessionLocal() as session:
                _save_kis_quote_snapshot(
                    session=session,
                    quote=quote,
                    fallback_name=str(candidate["name"]),
                    fallback_exchange=str(candidate["exchange"]),
                )
        except (MarketDataProviderUnavailable, SQLAlchemyError, ValueError):
            continue


def _auto_import_kis_supply_flows_for_strategy_candidates_if_needed(
    strategy_code: str,
    *,
    max_symbols: int = 12,
) -> None:
    if not is_kis_open_api_ready():
        return
    if _is_kis_supply_flow_in_cooldown():
        return

    safe_limit = max(1, min(max_symbols, 12))
    candidates = _seed_candidates_for_strategy(strategy_code, limit=safe_limit)
    symbols = [str(item["symbol"]) for item in candidates]
    if not symbols:
        return

    freshness_date = today_kst() - timedelta(days=5)
    try:
        with SessionLocal() as session:
            fresh_symbols = set(
                session.scalars(
                    select(Instrument.symbol)
                    .join(SupplyFlowDaily, SupplyFlowDaily.instrument_id == Instrument.id)
                    .where(
                        Instrument.symbol.in_(symbols),
                        SupplyFlowDaily.provider == KIS_SUPPLY_FLOW_PROVIDER,
                        SupplyFlowDaily.trade_date >= freshness_date,
                    )
                    .distinct()
                ).all()
            )
    except SQLAlchemyError:
        return

    for candidate in candidates:
        symbol = str(candidate["symbol"])
        if symbol in fresh_symbols:
            continue

        try:
            flows = fetch_kis_investor_trade_daily(symbol=symbol, base_date=today_kst(), limit=30)
            if not flows:
                continue
            with SessionLocal() as session:
                _save_kis_supply_flows(
                    session=session,
                    symbol=symbol,
                    name=str(candidate["name"]),
                    exchange=str(candidate["exchange"]),
                    flows=flows,
                )
        except MarketDataProviderUnavailable:
            _pause_kis_supply_flow_import(minutes=10)
            break
        except (SQLAlchemyError, ValueError):
            continue


def _is_kis_supply_flow_in_cooldown() -> bool:
    return KIS_SUPPLY_FLOW_COOLDOWN_UNTIL is not None and KIS_SUPPLY_FLOW_COOLDOWN_UNTIL > now_kst_naive()


def _pause_kis_supply_flow_import(*, minutes: int) -> None:
    global KIS_SUPPLY_FLOW_COOLDOWN_UNTIL
    KIS_SUPPLY_FLOW_COOLDOWN_UNTIL = now_kst_naive() + timedelta(minutes=minutes)


def _auto_import_kis_risk_indicators_for_strategy_candidates_if_needed(
    strategy_code: str,
    *,
    max_symbols: int = 12,
) -> None:
    if not is_kis_open_api_ready():
        return
    if _is_kis_risk_indicator_in_cooldown():
        return

    safe_limit = max(1, min(max_symbols, 8))
    candidates = _seed_candidates_for_strategy(strategy_code, limit=safe_limit)
    symbols = [str(item["symbol"]) for item in candidates]
    if not symbols:
        return

    freshness_date = today_kst() - timedelta(days=7)
    try:
        with SessionLocal() as session:
            fresh_symbols = set(
                session.scalars(
                    select(Instrument.symbol)
                    .join(RiskIndicatorDaily, RiskIndicatorDaily.instrument_id == Instrument.id)
                    .where(
                        Instrument.symbol.in_(symbols),
                        RiskIndicatorDaily.provider == KIS_RISK_INDICATOR_PROVIDER,
                        RiskIndicatorDaily.trade_date >= freshness_date,
                    )
                    .distinct()
                ).all()
            )
    except SQLAlchemyError:
        return

    for candidate in candidates:
        symbol = str(candidate["symbol"])
        if symbol in fresh_symbols:
            continue

        short_sale_rows: list[dict[str, object]] = []
        credit_balance_rows: list[dict[str, object]] = []
        should_pause = False
        try:
            short_sale_rows = fetch_kis_daily_short_sale(
                symbol=symbol,
                start=today_kst() - timedelta(days=45),
                end=today_kst(),
                limit=30,
            )
        except MarketDataProviderUnavailable as exc:
            if _is_kis_temporary_limit_error(exc):
                should_pause = True

        if not should_pause:
            try:
                credit_balance_rows = fetch_kis_daily_credit_balance(
                    symbol=symbol,
                    base_date=today_kst(),
                    limit=30,
                )
            except MarketDataProviderUnavailable as exc:
                if _is_kis_temporary_limit_error(exc):
                    should_pause = True

        if not short_sale_rows and not credit_balance_rows:
            if should_pause:
                _pause_kis_risk_indicator_import(minutes=10)
                break
            continue

        try:
            with SessionLocal() as session:
                _save_kis_risk_indicators(
                    session=session,
                    symbol=symbol,
                    name=str(candidate["name"]),
                    exchange=str(candidate["exchange"]),
                    short_sale_rows=short_sale_rows,
                    credit_balance_rows=credit_balance_rows,
                )

            if should_pause:
                _pause_kis_risk_indicator_import(minutes=10)
                break
        except (SQLAlchemyError, ValueError):
            continue


def _is_kis_risk_indicator_in_cooldown() -> bool:
    return KIS_RISK_INDICATOR_COOLDOWN_UNTIL is not None and KIS_RISK_INDICATOR_COOLDOWN_UNTIL > now_kst_naive()


def _pause_kis_risk_indicator_import(*, minutes: int) -> None:
    global KIS_RISK_INDICATOR_COOLDOWN_UNTIL
    KIS_RISK_INDICATOR_COOLDOWN_UNTIL = now_kst_naive() + timedelta(minutes=minutes)


def _auto_import_kis_fundamentals_for_strategy_candidates_if_needed(
    strategy_code: str,
    *,
    max_symbols: int = 6,
) -> None:
    if not is_kis_open_api_ready():
        return
    if _is_kis_fundamental_in_cooldown():
        return

    safe_limit = max(1, min(max_symbols, 4))
    candidates = _seed_candidates_for_strategy(strategy_code, limit=safe_limit)
    symbols = [str(item["symbol"]) for item in candidates]
    if not symbols:
        return

    try:
        with SessionLocal() as session:
            fresh_symbols = set(
                session.scalars(
                    select(Instrument.symbol)
                    .join(FundamentalRatio, FundamentalRatio.instrument_id == Instrument.id)
                    .where(
                        Instrument.symbol.in_(symbols),
                        FundamentalRatio.provider == KIS_FUNDAMENTAL_PROVIDER,
                        FundamentalRatio.period_type == "annual",
                    )
                    .distinct()
                ).all()
            )
    except SQLAlchemyError:
        return

    for candidate in candidates:
        symbol = str(candidate["symbol"])
        if symbol in fresh_symbols:
            continue

        try:
            rows = fetch_kis_financial_ratios(symbol=symbol, period_type="annual", limit=8)
            if not rows:
                continue
            with SessionLocal() as session:
                _save_kis_fundamental_ratios(
                    session=session,
                    symbol=symbol,
                    name=str(candidate["name"]),
                    exchange=str(candidate["exchange"]),
                    ratios=rows,
                )
        except MarketDataProviderUnavailable as exc:
            if _is_kis_temporary_limit_error(exc):
                _pause_kis_fundamental_import(minutes=10)
                break
            continue
        except (SQLAlchemyError, ValueError):
            continue


def _is_kis_fundamental_in_cooldown() -> bool:
    return KIS_FUNDAMENTAL_COOLDOWN_UNTIL is not None and KIS_FUNDAMENTAL_COOLDOWN_UNTIL > now_kst_naive()


def _pause_kis_fundamental_import(*, minutes: int) -> None:
    global KIS_FUNDAMENTAL_COOLDOWN_UNTIL
    KIS_FUNDAMENTAL_COOLDOWN_UNTIL = now_kst_naive() + timedelta(minutes=minutes)


def _auto_import_open_dart_fundamentals_for_strategy_candidates_if_needed(
    strategy_code: str,
    *,
    max_symbols: int = 6,
) -> None:
    if not is_open_dart_ready():
        return
    if _is_open_dart_fundamental_in_cooldown():
        return

    safe_limit = max(1, min(max_symbols, 4))
    candidates = _seed_candidates_for_strategy(strategy_code, limit=safe_limit)
    symbols = [str(item["symbol"]) for item in candidates]
    if not symbols:
        return

    try:
        with SessionLocal() as session:
            fresh_symbols = set(
                session.scalars(
                    select(Instrument.symbol)
                    .join(FundamentalRatio, FundamentalRatio.instrument_id == Instrument.id)
                    .where(
                        Instrument.symbol.in_(symbols),
                        FundamentalRatio.provider == OPEN_DART_FUNDAMENTAL_PROVIDER,
                        FundamentalRatio.period_type == "annual",
                        FundamentalRatio.fiscal_period.in_(
                            [f"{business_year}12" for business_year in _open_dart_candidate_business_years()]
                        ),
                    )
                    .distinct()
                ).all()
            )
    except SQLAlchemyError:
        return

    for candidate in candidates:
        symbol = str(candidate["symbol"])
        if symbol in fresh_symbols:
            continue

        try:
            business_year, _items, summary = _fetch_latest_open_dart_financial_summary(symbol=symbol)
            with SessionLocal() as session:
                _save_open_dart_fundamental_summary(
                    session=session,
                    symbol=symbol,
                    name=str(candidate["name"]),
                    exchange=str(candidate["exchange"]),
                    business_year=business_year,
                    summary=summary,
                )
        except MarketDataProviderUnavailable as exc:
            if _is_open_dart_temporary_limit_error(exc):
                _pause_open_dart_fundamental_import(minutes=30)
                break
            continue
        except (SQLAlchemyError, ValueError):
            continue


def _open_dart_candidate_business_years(max_years: int = 3) -> list[int]:
    latest_year = today_kst().year - 1
    earliest_year = max(2015, latest_year - max(1, max_years) + 1)
    return list(range(latest_year, earliest_year - 1, -1))


def _fetch_latest_open_dart_financial_summary(
    *,
    symbol: str,
    report_code: str = "11011",
    fs_div: str = "CFS",
) -> tuple[int, list[dict[str, object]], dict[str, object]]:
    for business_year in _open_dart_candidate_business_years():
        items = fetch_open_dart_financial_statements(
            symbol=symbol,
            business_year=business_year,
            report_code=report_code,
            fs_div=fs_div,
        )
        if not items:
            continue

        summary = summarize_open_dart_financial_statements(items)
        if any(value is not None for value in summary.values()):
            return business_year, items, summary

    raise MarketDataProviderUnavailable(f"OpenDART에서 {symbol}의 최근 사업보고서 재무요약을 찾지 못했습니다.")


def _is_open_dart_fundamental_in_cooldown() -> bool:
    return OPEN_DART_FUNDAMENTAL_COOLDOWN_UNTIL is not None and OPEN_DART_FUNDAMENTAL_COOLDOWN_UNTIL > now_kst_naive()


def _pause_open_dart_fundamental_import(*, minutes: int) -> None:
    global OPEN_DART_FUNDAMENTAL_COOLDOWN_UNTIL
    OPEN_DART_FUNDAMENTAL_COOLDOWN_UNTIL = now_kst_naive() + timedelta(minutes=minutes)


def _is_open_dart_temporary_limit_error(exc: MarketDataProviderUnavailable) -> bool:
    message = str(exc)
    temporary_fragments = (
        "사용한도를 초과",
        "사용한도",
        "too many",
        "429",
        "temporarily",
        "timeout",
    )
    return any(fragment in message for fragment in temporary_fragments)


def _is_kis_temporary_limit_error(exc: MarketDataProviderUnavailable) -> bool:
    message = str(exc)
    temporary_fragments = (
        "초당",
        "거래건수",
        "TIME LIMIT",
        "time limit",
        "temporarily",
        "429",
    )
    return any(fragment in message for fragment in temporary_fragments)


def _should_try_kis_candidate_import(
    daily_price_candidates: tuple[str, list[dict[str, object]]] | None,
) -> bool:
    if not is_kis_open_api_ready():
        return False
    provider_priority = _daily_price_provider_priority()
    if "KIS Open API" not in provider_priority:
        return False
    if daily_price_candidates is None:
        return True

    source, _candidates = daily_price_candidates
    current_provider = _source_primary_daily_price_provider(source)
    if current_provider not in provider_priority:
        return True
    if current_provider == "KIS Open API":
        return True
    return provider_priority.index("KIS Open API") < provider_priority.index(current_provider)


def _source_primary_daily_price_provider(source: str) -> str:
    if not source.startswith("daily-price-candidates:"):
        return ""
    provider_label = source.removeprefix("daily-price-candidates:").split(":")[0]
    return provider_label.split(" + ")[0].strip()


def _candidate_result_count(
    daily_price_candidates: tuple[str, list[dict[str, object]]] | None,
) -> int:
    if daily_price_candidates is None:
        return 0
    return len(daily_price_candidates[1])


def _candidate_target_count(limit: int) -> int:
    if limit <= 12:
        return min(max(1, limit), 10)
    return min(max(1, limit), 24)


def _load_strategy_candidate_result(
    strategy_code: str,
    *,
    limit: int = 12,
    auto_import: bool = True,
) -> tuple[str, list[dict[str, object]]] | None:
    safe_limit = max(1, min(limit, 100))
    target_count = _candidate_target_count(safe_limit)
    daily_price_candidates = _build_daily_price_strategy_candidates_if_available(
        strategy_code,
        limit=safe_limit,
    )

    if not auto_import:
        return daily_price_candidates

    daily_price_is_stale = _candidate_daily_price_data_is_stale(daily_price_candidates)
    if (
        _should_try_kis_candidate_import(daily_price_candidates)
        or _candidate_result_count(daily_price_candidates) < target_count
        or (is_kis_open_api_ready() and daily_price_is_stale)
    ):
        kis_imported = _auto_import_kis_daily_prices_for_strategy_candidates_if_needed(
            strategy_code,
            max_symbols=min(10, target_count),
        )
        if kis_imported:
            refreshed_kis_candidates = _build_daily_price_strategy_candidates_if_available(
                strategy_code,
                limit=safe_limit,
            )
            if refreshed_kis_candidates is not None:
                daily_price_candidates = refreshed_kis_candidates

    if _candidate_result_count(daily_price_candidates) < target_count:
        _auto_import_yahoo_daily_prices_for_strategy_candidates_if_needed(
            strategy_code,
            max_symbols=max(target_count, min(safe_limit, 30)),
        )
        refreshed_yahoo_candidates = _build_daily_price_strategy_candidates_if_available(
            strategy_code,
            limit=safe_limit,
        )
        if refreshed_yahoo_candidates is not None:
            daily_price_candidates = refreshed_yahoo_candidates

    if daily_price_candidates is not None:
        _auto_import_kis_fundamentals_for_strategy_candidates_if_needed(
            strategy_code,
            max_symbols=min(target_count, 4),
        )
        _auto_import_open_dart_fundamentals_for_strategy_candidates_if_needed(
            strategy_code,
            max_symbols=min(target_count, 4),
        )
        _auto_import_kis_supply_flows_for_strategy_candidates_if_needed(
            strategy_code,
            max_symbols=min(target_count, 12),
        )
        _auto_import_kis_risk_indicators_for_strategy_candidates_if_needed(
            strategy_code,
            max_symbols=min(target_count, 8),
        )
        _auto_import_kis_quote_snapshots_for_candidates_if_needed(
            candidates=daily_price_candidates[1],
            max_symbols=min(safe_limit, _kis_current_quote_refresh_max_symbols()),
        )
        refreshed_snapshot_candidates = _build_daily_price_strategy_candidates_if_available(
            strategy_code,
            limit=safe_limit,
        )
        if refreshed_snapshot_candidates is not None:
            daily_price_candidates = refreshed_snapshot_candidates

    return daily_price_candidates


def _candidate_daily_price_data_is_stale(
    daily_price_candidates: tuple[str, list[dict[str, object]]] | None,
) -> bool:
    if daily_price_candidates is None:
        return True

    _source, candidates = daily_price_candidates
    freshness = _build_data_freshness_for_candidates(candidates)
    return freshness.daily_price_status in {"missing", "stale", "unknown"}


def _candidate_price_start_date() -> date:
    today = today_kst()
    return date(max(today.year - 5, 1990), 1, 1)


def _load_strategy_candidate_price_rows(
    *,
    session,
    symbols: list[str],
    start_date: date,
    end_date: date,
) -> tuple[list[dict[str, object]], str]:
    provider_priority = _daily_price_provider_priority()
    rows = session.execute(
        select(
            Instrument.symbol,
            Instrument.name,
            Instrument.exchange,
            DailyPrice.trade_date,
            DailyPrice.open_price,
            DailyPrice.high_price,
            DailyPrice.low_price,
            DailyPrice.close_price,
            DailyPrice.volume,
            DailyPrice.trading_value,
            DailyPrice.provider,
        )
        .join(Instrument, Instrument.id == DailyPrice.instrument_id)
        .where(
            Instrument.symbol.in_(symbols),
            DailyPrice.trade_date >= start_date,
            DailyPrice.trade_date <= end_date,
            DailyPrice.is_adjusted.is_(False),
            DailyPrice.provider.in_(provider_priority),
        )
        .order_by(Instrument.symbol, DailyPrice.provider, DailyPrice.trade_date)
    ).all()

    grouped_by_provider: dict[str, list[dict[str, object]]] = {provider: [] for provider in provider_priority}
    for row in rows:
        grouped_by_provider[row.provider].append(
            {
                "symbol": row.symbol,
                "name": row.name,
                "exchange": row.exchange,
                "trade_date": row.trade_date,
                "open_price": row.open_price,
                "high_price": row.high_price,
                "low_price": row.low_price,
                "close_price": row.close_price,
                "volume": row.volume,
                "trading_value": row.trading_value,
                "provider": row.provider,
            }
        )

    minimum_symbols = min(10, len(symbols))
    best_rows: list[dict[str, object]] = []
    best_provider = ""
    best_symbol_count = 0

    for provider in provider_priority:
        provider_rows = _filter_candidate_price_rows_for_coverage(grouped_by_provider[provider])
        provider_symbol_count = _candidate_price_symbol_count(provider_rows)
        if (
            _has_candidate_price_coverage(provider_rows, minimum_symbols=minimum_symbols)
            and provider_symbol_count > best_symbol_count
        ):
            best_rows = provider_rows
            best_provider = provider
            best_symbol_count = provider_symbol_count

    mixed_rows, mixed_provider = _build_mixed_candidate_price_rows(
        grouped_by_provider=grouped_by_provider,
        provider_priority=provider_priority,
    )
    mixed_symbol_count = _candidate_price_symbol_count(mixed_rows)
    if (
        _has_candidate_price_coverage(mixed_rows, minimum_symbols=minimum_symbols)
        and mixed_symbol_count > best_symbol_count
    ):
        return mixed_rows, mixed_provider

    if best_rows:
        return best_rows, best_provider

    return [], ""


def _filter_candidate_price_rows_for_coverage(
    price_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows_by_symbol: dict[str, list[dict[str, object]]] = {}
    for row in price_rows:
        rows_by_symbol.setdefault(str(row["symbol"]), []).append(row)

    covered_rows: list[dict[str, object]] = []
    for rows in rows_by_symbol.values():
        if len(rows) >= 20:
            covered_rows.extend(rows)

    return covered_rows


def _has_candidate_price_coverage(
    price_rows: list[dict[str, object]],
    *,
    minimum_symbols: int,
) -> bool:
    symbols_count = _candidate_price_symbol_count(price_rows)
    return symbols_count >= minimum_symbols and len(price_rows) >= minimum_symbols * 20


def _candidate_price_symbol_count(price_rows: list[dict[str, object]]) -> int:
    return len({str(row["symbol"]) for row in price_rows})


def _build_mixed_candidate_price_rows(
    *,
    grouped_by_provider: dict[str, list[dict[str, object]]],
    provider_priority: list[str],
) -> tuple[list[dict[str, object]], str]:
    rows_by_symbol_provider: dict[str, dict[str, list[dict[str, object]]]] = {}

    for provider, rows in grouped_by_provider.items():
        for row in rows:
            symbol = str(row["symbol"])
            rows_by_symbol_provider.setdefault(symbol, {}).setdefault(provider, []).append(row)

    mixed_rows: list[dict[str, object]] = []
    used_providers: list[str] = []

    for provider_rows in rows_by_symbol_provider.values():
        for provider in provider_priority:
            covered_rows = _filter_candidate_price_rows_for_coverage(provider_rows.get(provider, []))
            if _has_candidate_price_coverage(covered_rows, minimum_symbols=1):
                mixed_rows.extend(covered_rows)
                if provider not in used_providers:
                    used_providers.append(provider)
                break

    return mixed_rows, _mixed_provider_label(used_providers)


def _load_latest_quote_snapshots_by_symbol(
    *,
    session,
    symbols: list[str],
) -> dict[str, dict[str, object]]:
    if not symbols:
        return {}

    conditions = [
        Instrument.symbol.in_(symbols),
        QuoteSnapshot.provider == KIS_QUOTE_SNAPSHOT_PROVIDER,
        QuoteSnapshot.snapshot_date == today_kst(),
    ]
    max_age_minutes = _kis_current_quote_max_age_minutes()
    if max_age_minutes > 0:
        conditions.append(QuoteSnapshot.created_at >= now_kst_naive() - timedelta(minutes=max_age_minutes))

    rows = session.execute(
        select(Instrument.symbol, QuoteSnapshot)
        .join(Instrument, Instrument.id == QuoteSnapshot.instrument_id)
        .where(*conditions)
        .order_by(Instrument.symbol, QuoteSnapshot.snapshot_date.desc(), QuoteSnapshot.id.desc())
    ).all()

    snapshots: dict[str, dict[str, object]] = {}
    for symbol, snapshot in rows:
        normalized_symbol = str(symbol)
        if normalized_symbol in snapshots:
            continue

        snapshots[normalized_symbol] = {
            "snapshot_date": snapshot.snapshot_date,
            "provider": snapshot.provider,
            "price": snapshot.price,
            "change_pct": snapshot.change_pct,
            "volume": snapshot.volume,
            "trading_value": snapshot.trading_value,
            "market_cap": snapshot.market_cap,
            "per": snapshot.per,
            "pbr": snapshot.pbr,
            "eps": snapshot.eps,
            "bps": snapshot.bps,
            "turnover_pct": snapshot.turnover_pct,
            "foreign_holding_rate": snapshot.foreign_holding_rate,
            "foreign_net_buy_qty": snapshot.foreign_net_buy_qty,
            "program_net_buy_qty": snapshot.program_net_buy_qty,
            "high_52w": snapshot.high_52w,
            "low_52w": snapshot.low_52w,
        }

    return snapshots


def _load_supply_flow_metrics_by_symbol(
    *,
    session,
    symbols: list[str],
) -> dict[str, dict[str, object]]:
    if not symbols:
        return {}

    rows = session.execute(
        select(Instrument.symbol, SupplyFlowDaily)
        .join(Instrument, Instrument.id == SupplyFlowDaily.instrument_id)
        .where(
            Instrument.symbol.in_(symbols),
            SupplyFlowDaily.provider == KIS_SUPPLY_FLOW_PROVIDER,
            SupplyFlowDaily.trade_date >= today_kst() - timedelta(days=80),
        )
        .order_by(Instrument.symbol, SupplyFlowDaily.trade_date.desc())
    ).all()

    rows_by_symbol: dict[str, list[SupplyFlowDaily]] = {}
    for symbol, flow in rows:
        rows_by_symbol.setdefault(str(symbol), []).append(flow)

    metrics: dict[str, dict[str, object]] = {}
    for symbol, flows in rows_by_symbol.items():
        ordered = sorted(flows, key=lambda item: item.trade_date, reverse=True)
        latest_5 = ordered[:5]
        latest_20 = ordered[:20]
        foreign_5 = _sum_decimal_value(latest_5, "foreign_net_buy_value")
        institution_5 = _sum_decimal_value(latest_5, "institution_net_buy_value")
        foreign_20 = _sum_decimal_value(latest_20, "foreign_net_buy_value")
        institution_20 = _sum_decimal_value(latest_20, "institution_net_buy_value")
        pension_20 = _sum_decimal_value(latest_20, "pension_net_buy_value")
        consecutive_foreign_buy_days = 0
        for flow in ordered:
            value = _decimal_or_none(flow.foreign_net_buy_value)
            if value is None or value <= 0:
                break
            consecutive_foreign_buy_days += 1

        metrics[symbol] = {
            "foreign_net_buy_5d": _krw_to_100m(foreign_5),
            "institution_net_buy_5d": _krw_to_100m(institution_5),
            "foreign_net_buy_20d": _krw_to_100m(foreign_20),
            "institution_net_buy_20d": _krw_to_100m(institution_20),
            "pension_net_buy_20d": _krw_to_100m(pension_20),
            "consecutive_foreign_buy_days": consecutive_foreign_buy_days,
            "supply_score": _supply_flow_score(
                foreign_5=_krw_to_100m(foreign_5),
                institution_5=_krw_to_100m(institution_5),
                foreign_20=_krw_to_100m(foreign_20),
                institution_20=_krw_to_100m(institution_20),
                consecutive_foreign_buy_days=consecutive_foreign_buy_days,
            ),
        }

    return metrics


def _load_fundamental_metrics_by_symbol(
    *,
    session,
    symbols: list[str],
) -> dict[str, dict[str, object]]:
    if not symbols:
        return {}

    rows = session.execute(
        select(Instrument.symbol, FundamentalRatio)
        .join(Instrument, Instrument.id == FundamentalRatio.instrument_id)
        .where(
            Instrument.symbol.in_(symbols),
            FundamentalRatio.provider.in_([KIS_FUNDAMENTAL_PROVIDER, OPEN_DART_FUNDAMENTAL_PROVIDER]),
            FundamentalRatio.period_type == "annual",
        )
        .order_by(Instrument.symbol, FundamentalRatio.provider, FundamentalRatio.fiscal_period.desc())
    ).all()

    rows_by_symbol_provider: dict[str, dict[str, list[FundamentalRatio]]] = {}
    for symbol, ratio in rows:
        rows_by_symbol_provider.setdefault(str(symbol), {}).setdefault(ratio.provider, []).append(ratio)

    metrics: dict[str, dict[str, object]] = {}
    for normalized_symbol, ratios_by_provider in rows_by_symbol_provider.items():
        merged: dict[str, object] = {}
        provider_labels: list[str] = []
        for provider in (KIS_FUNDAMENTAL_PROVIDER, OPEN_DART_FUNDAMENTAL_PROVIDER):
            ratio = _select_fundamental_ratio_for_candidate(ratios_by_provider.get(provider, []))
            if ratio is None:
                continue
            provider_labels.append(FUNDAMENTAL_PROVIDER_LABELS.get(provider, provider))
            provider_values = {
                "fiscal_period": ratio.fiscal_period,
                "revenue_growth": _decimal_or_float(ratio.revenue_growth),
                "operating_income_growth": _decimal_or_float(ratio.operating_income_growth),
                "net_income_growth": _decimal_or_float(ratio.net_income_growth),
                "roe": _decimal_or_float(ratio.roe),
                "roa": _decimal_or_float(ratio.roa),
                "operating_margin": _decimal_or_float(ratio.operating_margin),
                "net_margin": _decimal_or_float(ratio.net_margin),
                "free_cash_flow": _decimal_or_float(ratio.free_cash_flow),
                "dividends_paid": _decimal_or_float(ratio.dividends_paid),
                "current_assets": _decimal_or_float(ratio.current_assets),
                "current_liabilities": _decimal_or_float(ratio.current_liabilities),
                "cash_and_cash_equivalents": _decimal_or_float(ratio.cash_and_cash_equivalents),
                "ebitda": _decimal_or_float(ratio.ebitda),
                "fcf_yield": _decimal_or_float(ratio.fcf_yield),
                "ev_ebitda": _decimal_or_float(ratio.ev_ebitda),
                "dividend_yield": _decimal_or_float(ratio.dividend_yield),
                "payout_ratio": _decimal_or_float(ratio.payout_ratio),
                "current_ratio": _decimal_or_float(ratio.current_ratio),
                "dividend_growth": _decimal_or_float(ratio.dividend_growth),
                "dividend_streak_years": ratio.dividend_streak_years,
                "dividend_stability_score": ratio.dividend_stability_score,
                "eps": _decimal_or_float(ratio.eps),
                "sps": _decimal_or_float(ratio.sps),
                "bps": _decimal_or_float(ratio.bps),
                "reserve_ratio": _decimal_or_float(ratio.reserve_ratio),
                "debt_ratio": _decimal_or_float(ratio.debt_ratio),
            }
            for key, value in provider_values.items():
                if value is not None:
                    merged[key] = value

        if merged:
            dividend_streak_years = _dividend_streak_years_from_ratios(
                ratios_by_provider.get(OPEN_DART_FUNDAMENTAL_PROVIDER, [])
            )
            if dividend_streak_years is not None:
                merged["dividend_streak_years"] = dividend_streak_years
            merged["provider_label"] = " + ".join(provider_labels)
            metrics[normalized_symbol] = merged

    return metrics


def _select_fundamental_ratio_for_candidate(ratios: list[FundamentalRatio]) -> FundamentalRatio | None:
    if not ratios:
        return None

    ordered = sorted(ratios, key=lambda item: item.fiscal_period, reverse=True)
    annual_closing_rows = [ratio for ratio in ordered if ratio.fiscal_period.endswith("12")]
    if annual_closing_rows:
        return annual_closing_rows[0]

    non_empty_rows = [
        ratio
        for ratio in ordered
        if any(
            value is not None
            for value in (
                ratio.revenue_growth,
                ratio.operating_income_growth,
                ratio.net_income_growth,
                ratio.roe,
                ratio.roa,
                ratio.operating_margin,
                ratio.net_margin,
                ratio.free_cash_flow,
                ratio.dividends_paid,
                ratio.current_ratio,
                ratio.ebitda,
                ratio.fcf_yield,
                ratio.ev_ebitda,
                ratio.dividend_yield,
                ratio.payout_ratio,
                ratio.dividend_growth,
                ratio.dividend_streak_years,
                ratio.dividend_stability_score,
                ratio.debt_ratio,
            )
        )
    ]
    return non_empty_rows[0] if non_empty_rows else ordered[0]


def _dividend_streak_years_from_ratios(ratios: list[FundamentalRatio]) -> int | None:
    yearly_rows: dict[int, FundamentalRatio] = {}
    for ratio in ratios:
        if ratio.dividends_paid is None:
            continue
        try:
            fiscal_year = int(str(ratio.fiscal_period)[:4])
        except ValueError:
            continue
        existing = yearly_rows.get(fiscal_year)
        if existing is None or str(ratio.fiscal_period) > str(existing.fiscal_period):
            yearly_rows[fiscal_year] = ratio

    if not yearly_rows:
        return None

    streak = 0
    expected_year: int | None = None
    for fiscal_year in sorted(yearly_rows, reverse=True):
        if expected_year is not None and fiscal_year != expected_year:
            break
        dividends_paid = _decimal_or_none(yearly_rows[fiscal_year].dividends_paid)
        if dividends_paid is None or dividends_paid <= 0:
            break
        streak += 1
        expected_year = fiscal_year - 1

    return streak


def _load_risk_indicator_metrics_by_symbol(
    *,
    session,
    symbols: list[str],
) -> dict[str, dict[str, object]]:
    if not symbols:
        return {}

    rows = session.execute(
        select(Instrument.symbol, RiskIndicatorDaily)
        .join(Instrument, Instrument.id == RiskIndicatorDaily.instrument_id)
        .where(
            Instrument.symbol.in_(symbols),
            RiskIndicatorDaily.provider == KIS_RISK_INDICATOR_PROVIDER,
            RiskIndicatorDaily.trade_date >= today_kst() - timedelta(days=90),
        )
        .order_by(Instrument.symbol, RiskIndicatorDaily.trade_date.desc())
    ).all()

    rows_by_symbol: dict[str, list[RiskIndicatorDaily]] = {}
    for symbol, indicator in rows:
        rows_by_symbol.setdefault(str(symbol), []).append(indicator)

    metrics: dict[str, dict[str, object]] = {}
    for symbol, indicators in rows_by_symbol.items():
        ordered = sorted(indicators, key=lambda item: item.trade_date, reverse=True)
        latest_short_sale_ratio = _latest_decimal_value(
            ordered,
            "short_sale_volume_ratio",
            fallback_field="short_sale_value_ratio",
        )
        margin_debt_change_5d = _margin_debt_change_pct(ordered[:10])

        metrics[symbol] = {
            "short_sale_ratio": float(latest_short_sale_ratio) if latest_short_sale_ratio is not None else None,
            "margin_debt_change_5d": margin_debt_change_5d,
        }

    return metrics


def _latest_decimal_value(
    rows: list[object],
    field: str,
    *,
    fallback_field: str | None = None,
) -> Decimal | None:
    for row in rows:
        value = _decimal_or_none(getattr(row, field))
        if value is not None:
            return value
        if fallback_field:
            fallback_value = _decimal_or_none(getattr(row, fallback_field))
            if fallback_value is not None:
                return fallback_value
    return None


def _margin_debt_change_pct(rows: list[RiskIndicatorDaily]) -> float:
    balances = [
        _decimal_or_none(row.margin_loan_balance)
        for row in sorted(rows, key=lambda item: item.trade_date)
        if _decimal_or_none(row.margin_loan_balance) is not None
    ]
    if len(balances) < 2:
        return 0.0

    start_balance = balances[0]
    end_balance = balances[-1]
    if start_balance is None or end_balance is None or start_balance <= 0:
        return 0.0

    return round(float((end_balance / start_balance - 1) * 100), 2)


def _sum_decimal_value(rows: list[object], field: str) -> Decimal:
    total = Decimal("0")
    for row in rows:
        value = _decimal_or_none(getattr(row, field))
        if value is not None:
            total += value
    return total


def _krw_to_100m(value: Decimal) -> int:
    return round(value / Decimal("100000000"))


def _supply_flow_score(
    *,
    foreign_5: int,
    institution_5: int,
    foreign_20: int,
    institution_20: int,
    consecutive_foreign_buy_days: int,
) -> int:
    score = (
        50
        + min(max(foreign_5, 0) / 40, 16)
        + min(max(institution_5, 0) / 40, 16)
        + min(max(foreign_20, 0) / 120, 10)
        + min(max(institution_20, 0) / 120, 10)
        + min(consecutive_foreign_buy_days * 2, 8)
    )
    return max(0, min(100, round(score)))


def _mixed_provider_label(providers: list[str]) -> str:
    if not providers:
        return ""
    return " + ".join(providers)


def _resolve_strategy_candidate_response(
    strategy_code: str,
    limit: int = 12,
    *,
    auto_import: bool = True,
) -> StrategyCandidateResponse:
    safe_limit = max(1, min(limit, 100))
    strategy = _find_system_strategy(strategy_code)
    strategy_name = strategy.name if strategy else ""
    user_strategy = None
    source = "sample-engine"
    candidates = []

    if strategy is None and strategy_code.startswith("user-"):
        user_strategy = _load_active_user_strategy(strategy_code)
        if user_strategy is not None:
            strategy_name = user_strategy.name
            source = "sample-engine:user-strategy"

    if strategy is None and not strategy_name:
        raise HTTPException(status_code=404, detail="전략을 찾지 못했습니다.")

    if strategy is not None:
        daily_price_candidates = _load_strategy_candidate_result(
            strategy_code,
            limit=safe_limit,
            auto_import=auto_import,
        )
        if daily_price_candidates is not None:
            source, candidates = daily_price_candidates

    if user_strategy is not None:
        daily_price_candidates = _load_strategy_candidate_result(
            strategy_code,
            limit=safe_limit,
            auto_import=auto_import,
        )
        if daily_price_candidates is not None:
            source, candidates = daily_price_candidates

    if not candidates:
        candidates = build_strategy_candidates(strategy_code=strategy_code, limit=safe_limit)

    if user_strategy is not None:
        candidates, _unsupported_conditions = apply_user_strategy_formula(
            candidates=candidates,
            formula=user_strategy.formula,
        )
        source = f"{source}:filtered"

    return StrategyCandidateResponse(
        strategy_code=strategy_code,
        strategy_name=strategy_name,
        source=source,
        data_freshness=_build_data_freshness_for_candidates(candidates),
        candidates=[StrategyCandidate(**candidate) for candidate in candidates],
    )


def _strategy_execution_contract(strategy_code: str) -> StrategyExecutionContractResponse:
    strategy = _find_system_strategy(strategy_code)
    user_strategy = None
    formula = ""

    if strategy is None and strategy_code.startswith("user-"):
        user_strategy = _load_active_user_strategy(strategy_code)

    if strategy is None and user_strategy is None:
        raise HTTPException(status_code=404, detail="전략을 찾지 못했습니다.")

    if strategy is not None:
        strategy_name = strategy.name
        source_type = strategy.source_type
        summary = strategy.summary
        formula = " AND ".join(strategy.signal_rules)
    else:
        strategy_name = user_strategy.name
        source_type = "user"
        summary = user_strategy.summary
        formula = user_strategy.formula

    paper_order_ready = is_kis_paper_trading() and _paper_trading_enabled() and not _emergency_stop_enabled()
    modes = [
        StrategyExecutionModeContract(
            code="screen",
            label="전략 후보 검색",
            enabled=True,
            endpoint=f"/api/strategies/{strategy_code}/candidates",
            note="전략 정의와 저장된 검색식을 사용해 후보 종목을 산출합니다.",
        ),
        StrategyExecutionModeContract(
            code="screener",
            label="검색기 조건 적용",
            enabled=True,
            endpoint="/api/screener/search",
            note="검색기 조건식과 같은 필드 계약을 사용합니다.",
        ),
        StrategyExecutionModeContract(
            code="backtest",
            label="백테스트",
            enabled=True,
            endpoint="/api/backtests/run",
            note="동일 전략 코드로 과거 일봉 기반 동적 리밸런싱을 실행합니다.",
        ),
        StrategyExecutionModeContract(
            code="paper-order-proposal",
            label="모의 주문 제안",
            enabled=is_kis_open_api_ready() and has_kis_account_credentials(),
            endpoint="/api/broker/kis/order-proposals",
            note="전략 후보를 종목당 금액과 주문 가능 수량으로 변환합니다.",
        ),
        StrategyExecutionModeContract(
            code="paper-order-submit",
            label="모의 일괄 주문",
            enabled=paper_order_ready,
            endpoint="/api/broker/kis/paper/orders/batch",
            note="확인 문구, 주문 한도, 일일 횟수, 긴급 중지, 손실 중지 안전장치를 통과해야 합니다.",
        ),
        StrategyExecutionModeContract(
            code="live-order-submit",
            label="실전 일괄 주문",
            enabled=False,
            endpoint="",
            note="실전 주문 API는 아직 열지 않았고, 별도 검토 후 추가합니다.",
        ),
    ]

    return StrategyExecutionContractResponse(
        strategy_code=strategy_code,
        strategy_name=strategy_name,
        source_type=source_type,
        summary=summary,
        formula=formula,
        provider_priority=_daily_price_provider_priority(),
        backtest_policy=backtest_policy_for_strategy(strategy_code),
        safety_controls=[
            "PAPER_TRADING_ENABLED",
            "EMERGENCY_STOP_ENABLED",
            "MANUAL_ORDER_CONFIRMATION_REQUIRED",
            "MAX_ORDER_AMOUNT_KRW",
            "MAX_DAILY_ORDER_COUNT",
            "DAILY_LOSS_STOP_ENABLED",
            "MAX_DAILY_LOSS_KRW",
        ],
        modes=modes,
    )


def _search_screener_response(request: ScreenerSearchRequest) -> ScreenerSearchResponse:
    base_response = _resolve_strategy_candidate_response(
        request.strategy_code,
        limit=request.limit,
        auto_import=False,
    )
    candidates = [candidate.model_dump() for candidate in base_response.candidates]
    unsupported_conditions: list[str] = []
    formula = request.formula.strip()

    if formula and not formula.startswith("필터를 선택하면"):
        candidates, unsupported_conditions = apply_user_strategy_formula(
            candidates=candidates,
            formula=formula,
        )

    source = base_response.source
    if formula and not formula.startswith("필터를 선택하면"):
        source = f"{source}:screener-filtered"

    visible_candidates = candidates[: request.limit]
    if visible_candidates and is_kis_open_api_ready():
        _auto_import_kis_quote_snapshots_for_candidates_if_needed(
            candidates=visible_candidates,
            max_symbols=min(len(visible_candidates), _kis_current_quote_refresh_max_symbols()),
        )
        visible_candidates, enriched_with_quotes = _enrich_candidates_with_current_quote_snapshots(
            visible_candidates
        )
        if enriched_with_quotes and "KIS 현재가" not in source:
            source = f"{source} + KIS 현재가"

    return ScreenerSearchResponse(
        strategy_code=base_response.strategy_code,
        strategy_name=base_response.strategy_name,
        source=source,
        data_freshness=_build_data_freshness_for_candidates(visible_candidates),
        unsupported_conditions=unsupported_conditions,
        candidates=[StrategyCandidate(**candidate) for candidate in visible_candidates],
    )


def _enrich_candidates_with_current_quote_snapshots(
    candidates: list[dict[str, object]],
) -> tuple[list[dict[str, object]], bool]:
    symbols = [str(candidate.get("symbol") or "").strip().upper() for candidate in candidates]
    symbols = [symbol for symbol in symbols if symbol]
    if not symbols:
        return candidates, False

    try:
        with SessionLocal() as session:
            quote_snapshots = _load_latest_quote_snapshots_by_symbol(session=session, symbols=symbols)
    except SQLAlchemyError:
        return candidates, False

    if not quote_snapshots:
        return candidates, False

    enriched = enrich_strategy_candidates_with_quote_snapshots(
        candidates=candidates,
        quote_snapshots=quote_snapshots,
    )
    order_by_symbol = {
        str(candidate.get("symbol") or ""): index
        for index, candidate in enumerate(candidates)
    }
    enriched.sort(key=lambda candidate: order_by_symbol.get(str(candidate.get("symbol") or ""), 0))
    return enriched, True


def _build_data_freshness_for_candidates(
    candidates: list[dict[str, object]] | list[StrategyCandidate],
) -> DataFreshnessResponse:
    symbols: list[str] = []
    for candidate in candidates:
        symbol = (
            candidate.symbol
            if isinstance(candidate, StrategyCandidate)
            else str(candidate.get("symbol") or "")
        )
        normalized_symbol = symbol.strip().upper()
        if normalized_symbol and normalized_symbol not in symbols:
            symbols.append(normalized_symbol)
    return _build_data_freshness(symbols)


def _build_data_freshness(symbols: list[str]) -> DataFreshnessResponse:
    if not symbols:
        return DataFreshnessResponse(
            expected_daily_price_date=_expected_latest_daily_price_date(),
            daily_price_status="missing",
            message="후보 종목이 없어 데이터 기준일을 계산하지 않았습니다.",
            warnings=["후보 종목이 없어 전략 계산용 데이터 신선도를 확인하지 않았습니다."],
        )

    try:
        with SessionLocal() as session:
            instrument_ids = session.scalars(
                select(Instrument.id).where(Instrument.symbol.in_(symbols))
            ).all()

            if not instrument_ids:
                return DataFreshnessResponse(
                    expected_daily_price_date=_expected_latest_daily_price_date(),
                    daily_price_status="missing",
                    message="후보 종목의 저장 데이터가 아직 없습니다.",
                    warnings=["후보 종목의 DB 일봉이 없어 샘플 또는 제한된 데이터가 사용될 수 있습니다."],
                )

            latest_daily_price_date = session.scalar(
                select(func.max(DailyPrice.trade_date)).where(DailyPrice.instrument_id.in_(instrument_ids))
            )
            provider_rows = session.execute(
                select(DailyPrice.provider)
                .where(DailyPrice.instrument_id.in_(instrument_ids))
                .group_by(DailyPrice.provider)
                .order_by(DailyPrice.provider)
            ).all()
            latest_quote_snapshot_date = session.scalar(
                select(func.max(QuoteSnapshot.snapshot_date)).where(
                    QuoteSnapshot.instrument_id.in_(instrument_ids)
                )
            )
            latest_supply_flow_date = session.scalar(
                select(func.max(SupplyFlowDaily.trade_date)).where(
                    SupplyFlowDaily.instrument_id.in_(instrument_ids)
                )
            )
            latest_risk_indicator_date = session.scalar(
                select(func.max(RiskIndicatorDaily.trade_date)).where(
                    RiskIndicatorDaily.instrument_id.in_(instrument_ids)
                )
            )
            latest_fundamental_period = session.scalar(
                select(func.max(FundamentalRatio.fiscal_period)).where(
                    FundamentalRatio.instrument_id.in_(instrument_ids)
                )
            )
    except SQLAlchemyError:
        return DataFreshnessResponse(
            expected_daily_price_date=_expected_latest_daily_price_date(),
            daily_price_status="unknown",
            message="데이터 기준일을 계산하지 못했습니다.",
            warnings=["DB 오류로 데이터 신선도 상태를 확인하지 못했습니다."],
        )

    daily_price_providers = [str(row.provider) for row in provider_rows]
    expected_daily_price_date = _expected_latest_daily_price_date()
    daily_price_status, warnings = _daily_price_freshness_status(
        latest_daily_price_date=latest_daily_price_date,
        expected_daily_price_date=expected_daily_price_date,
    )
    return DataFreshnessResponse(
        latest_daily_price_date=latest_daily_price_date,
        expected_daily_price_date=expected_daily_price_date,
        daily_price_status=daily_price_status,
        daily_price_providers=daily_price_providers,
        latest_quote_snapshot_date=latest_quote_snapshot_date,
        latest_supply_flow_date=latest_supply_flow_date,
        latest_risk_indicator_date=latest_risk_indicator_date,
        latest_fundamental_period=str(latest_fundamental_period) if latest_fundamental_period else None,
        message=_data_freshness_message(
            latest_daily_price_date=latest_daily_price_date,
            expected_daily_price_date=expected_daily_price_date,
            daily_price_status=daily_price_status,
        ),
        warnings=warnings,
    )


def _expected_latest_daily_price_date() -> date:
    return previous_market_trading_day("KR", today_kst())


def _daily_price_freshness_status(
    *,
    latest_daily_price_date: date | None,
    expected_daily_price_date: date,
) -> tuple[str, list[str]]:
    if latest_daily_price_date is None:
        return "missing", ["전략 계산에 사용할 저장 일봉이 없습니다."]

    stale_days = (expected_daily_price_date - latest_daily_price_date).days
    if stale_days <= _strategy_daily_price_max_staleness_days():
        return "current", []

    return (
        "stale",
        [
            (
                f"전략 계산용 일봉이 {latest_daily_price_date.isoformat()} 기준입니다. "
                f"기대 기준일은 {expected_daily_price_date.isoformat()}입니다."
            )
        ],
    )


def _data_freshness_message(
    *,
    latest_daily_price_date: date | None,
    expected_daily_price_date: date,
    daily_price_status: str,
) -> str:
    if latest_daily_price_date is None:
        return "저장된 일봉 기준일이 없습니다."
    if daily_price_status == "current":
        return f"{latest_daily_price_date.isoformat()} 거래일 기준입니다."

    return (
        f"{latest_daily_price_date.isoformat()} 기준으로 지연된 데이터입니다. "
        f"기대 기준일은 {expected_daily_price_date.isoformat()}입니다."
    )


def _manual_refresh_job_response(job: dict[str, object]) -> ManualDataRefreshJobResponse:
    started_at = job["started_at"]
    if not isinstance(started_at, datetime):
        started_at = now_kst_naive()
    finished_at = job.get("finished_at")
    if not isinstance(finished_at, datetime):
        finished_at = None

    now = finished_at or now_kst_naive()
    elapsed_seconds = max(0, int((now - started_at).total_seconds()))
    progress_pct = int(job.get("progress_pct") or 0)
    estimated_remaining_seconds = None
    if job.get("status") == "running" and progress_pct > 0:
        estimated_total = int(elapsed_seconds * 100 / progress_pct)
        estimated_remaining_seconds = max(0, estimated_total - elapsed_seconds)

    return ManualDataRefreshJobResponse(
        job_id=str(job["job_id"]),
        status=str(job.get("status") or "unknown"),
        stage=str(job.get("stage") or "대기 중"),
        progress_pct=progress_pct,
        current_step=int(job.get("current_step") or 0),
        total_steps=int(job.get("total_steps") or 0),
        success_count=int(job.get("success_count") or 0),
        failed_count=int(job.get("failed_count") or 0),
        saved_count=int(job.get("saved_count") or 0),
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=elapsed_seconds,
        estimated_remaining_seconds=estimated_remaining_seconds,
        latest_daily_price_date=job.get("latest_daily_price_date") if isinstance(job.get("latest_daily_price_date"), date) else None,
        expected_daily_price_date=job.get("expected_daily_price_date") if isinstance(job.get("expected_daily_price_date"), date) else None,
        message=str(job.get("message") or ""),
        warnings=[str(item) for item in job.get("warnings", []) if item],
    )


def _get_manual_refresh_job(job_id: str) -> dict[str, object] | None:
    with MANUAL_DATA_REFRESH_LOCK:
        job = MANUAL_DATA_REFRESH_JOBS.get(job_id)
        return dict(job) if job is not None else None


def _update_manual_refresh_job(job_id: str, **updates: object) -> None:
    with MANUAL_DATA_REFRESH_LOCK:
        job = MANUAL_DATA_REFRESH_JOBS.get(job_id)
        if job is None:
            return
        job.update(updates)


def _latest_daily_price_date() -> date | None:
    try:
        with SessionLocal() as session:
            return session.scalar(select(func.max(DailyPrice.trade_date)))
    except SQLAlchemyError:
        return None


def _run_manual_data_refresh(job_id: str, request: ManualDataRefreshRequest) -> None:
    markets = [market.strip().upper() for market in request.markets if market.strip()]
    markets = [market for market in markets if market in {"KOSPI", "KOSDAQ", "KONEX"}]
    if not markets:
        markets = ["KOSPI", "KOSDAQ"]

    total_steps = (1 if request.refresh_instruments else 0) + (len(markets) if request.refresh_daily_prices else 0)
    total_steps = max(total_steps, 1)
    current_step = 0
    saved_count = 0
    success_count = 0
    failed_count = 0
    warnings: list[str] = []
    expected_date = _expected_latest_daily_price_date()
    start_date = expected_date - timedelta(days=request.lookback_days)

    def advance(stage: str, message: str) -> None:
        progress_pct = min(99, int(current_step / total_steps * 100))
        _update_manual_refresh_job(
            job_id,
            status="running",
            stage=stage,
            progress_pct=progress_pct,
            current_step=current_step,
            total_steps=total_steps,
            saved_count=saved_count,
            success_count=success_count,
            failed_count=failed_count,
            expected_daily_price_date=expected_date,
            message=message,
            warnings=warnings,
        )

    try:
        if request.refresh_instruments:
            advance("KRX 종목 마스터 갱신", "KRX 종목 목록을 가져오는 중입니다.")
            base_date = default_krx_base_date()
            rows = fetch_krx_instruments(market="ALL", limit=3000, base_date=base_date)
            response = _save_krx_instruments(market="ALL", base_date=base_date, rows=rows)
            current_step += 1
            success_count += 1
            advance("KRX 종목 마스터 저장", response.message)

        if request.refresh_daily_prices:
            for market in markets:
                advance(f"KRX {market} 일봉 갱신", f"{market} {start_date.isoformat()} ~ {expected_date.isoformat()} 일봉을 가져오는 중입니다.")
                prices = fetch_krx_market_daily_prices(market=market, start=start_date, end=expected_date)
                if not prices:
                    failed_count += 1
                    warnings.append(f"{market} KRX 일봉 데이터가 없습니다.")
                    current_step += 1
                    continue
                with SessionLocal() as session:
                    response = _save_krx_market_daily_prices(
                        session=session,
                        request=KrxMarketDailyPriceImportRequest(
                            market=market,
                            start=start_date,
                            end=expected_date,
                        ),
                        prices=prices,
                    )
                saved_count += response.saved_count
                success_count += 1
                current_step += 1
                advance(f"KRX {market} 일봉 저장", response.message)

        latest_date = _latest_daily_price_date()
        _update_manual_refresh_job(
            job_id,
            status="completed",
            stage="완료",
            progress_pct=100,
            current_step=total_steps,
            total_steps=total_steps,
            saved_count=saved_count,
            success_count=success_count,
            failed_count=failed_count,
            finished_at=now_kst_naive(),
            latest_daily_price_date=latest_date,
            expected_daily_price_date=expected_date,
            message=f"최신 데이터 갱신 완료: 저장 {saved_count:,}건",
            warnings=warnings,
        )
    except (MarketDataProviderUnavailable, SQLAlchemyError, ValueError) as exc:
        _update_manual_refresh_job(
            job_id,
            status="failed",
            stage="실패",
            progress_pct=max(1, int(current_step / total_steps * 100)),
            current_step=current_step,
            total_steps=total_steps,
            failed_count=failed_count + 1,
            finished_at=now_kst_naive(),
            latest_daily_price_date=_latest_daily_price_date(),
            expected_daily_price_date=expected_date,
            message=f"최신 데이터 갱신 실패: {exc}",
            warnings=warnings,
        )


def _save_strategy_selection_run(response: StrategyCandidateResponse) -> tuple[int | None, datetime | None]:
    payload = response.model_dump(mode="json")
    payload.pop("run_id", None)
    payload.pop("run_at", None)

    try:
        with SessionLocal() as session:
            run = StrategySelectionRun(
                strategy_code=response.strategy_code,
                strategy_name=response.strategy_name,
                source=response.source,
                result_count=len(response.candidates),
                result_json=json.dumps(payload, ensure_ascii=False),
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run.id, run.created_at
    except SQLAlchemyError:
        return None, None


def _strategy_selection_top_candidates(run: StrategySelectionRun) -> str:
    try:
        payload = json.loads(run.result_json)
    except json.JSONDecodeError:
        return ""

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return ""

    names: list[str] = []
    for item in candidates[:3]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("symbol") or "").strip()
        if name:
            names.append(name)

    return ", ".join(names)


def _strategy_selection_run_summary(run: StrategySelectionRun) -> StrategySelectionRunSummary:
    return StrategySelectionRunSummary(
        id=run.id,
        strategy_code=run.strategy_code,
        strategy_name=run.strategy_name,
        source=run.source,
        result_count=run.result_count,
        top_candidates=_strategy_selection_top_candidates(run),
        created_at=run.created_at,
    )


def _saved_strategy_selection_run_response(run: StrategySelectionRun) -> StrategyCandidateResponse:
    try:
        payload = json.loads(run.result_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="저장된 전략 실행 결과를 해석하지 못했습니다.") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="저장된 전략 실행 결과 형식이 올바르지 않습니다.")

    payload["run_id"] = run.id
    payload["run_at"] = run.created_at
    payload.setdefault("strategy_code", run.strategy_code)
    payload.setdefault("strategy_name", run.strategy_name)
    payload.setdefault("source", run.source)
    saved_candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
    payload.setdefault(
        "data_freshness",
        _build_data_freshness_for_candidates(saved_candidates).model_dump(mode="json"),
    )

    return StrategyCandidateResponse(**payload)


def _quality_check(
    *,
    code: str,
    label: str,
    status: str,
    value: str,
    message: str,
) -> DataQualityCheck:
    return DataQualityCheck(
        code=code,
        label=label,
        status=status,
        value=value,
        message=message,
    )


def _quality_summary_status(checks: list[DataQualityCheck]) -> str:
    if any(check.status == "error" for check in checks):
        return "error"
    if any(check.status == "warning" for check in checks):
        return "warning"
    return "ok"


def _provider_counts_label(rows: list[tuple[str, int]]) -> str:
    if not rows:
        return "없음"
    return ", ".join(f"{provider} {count:,}건" for provider, count in rows)


@app.get("/api/health")
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app="QuantMate API",
        mode=AppMode.RESEARCH,
        live_trading_enabled=_env_bool("LIVE_TRADING_ENABLED"),
    )


@app.get("/api/strategies")
async def list_strategies() -> list[Strategy]:
    return STRATEGIES


@app.get("/api/strategies/{strategy_code}/candidates")
async def strategy_candidates(
    strategy_code: str,
    limit: int = 12,
    refresh: bool = True,
) -> StrategyCandidateResponse:
    response = await run_in_threadpool(
        _resolve_strategy_candidate_response,
        strategy_code,
        limit=limit,
        auto_import=refresh,
    )
    run_id, run_at = _save_strategy_selection_run(response)
    response.run_id = run_id
    response.run_at = run_at
    return response


@app.get("/api/strategies/{strategy_code}/contract")
async def strategy_execution_contract(strategy_code: str) -> StrategyExecutionContractResponse:
    return _strategy_execution_contract(strategy_code)


@app.get("/api/strategy-runs")
async def list_strategy_selection_runs(limit: int = 10) -> list[StrategySelectionRunSummary]:
    safe_limit = max(1, min(limit, 50))

    try:
        with SessionLocal() as session:
            runs = session.scalars(
                select(StrategySelectionRun)
                .order_by(StrategySelectionRun.created_at.desc(), StrategySelectionRun.id.desc())
                .limit(safe_limit)
            ).all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"전략 실행 결과 DB 조회 실패: {exc.__class__.__name__}",
        ) from exc

    return [_strategy_selection_run_summary(run) for run in runs]


@app.get("/api/strategy-runs/{run_id}")
async def get_strategy_selection_run(run_id: int) -> StrategyCandidateResponse:
    try:
        with SessionLocal() as session:
            run = session.get(StrategySelectionRun, run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="전략 실행 결과를 찾지 못했습니다.")

            return _saved_strategy_selection_run_response(run)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"전략 실행 결과 DB 조회 실패: {exc.__class__.__name__}",
        ) from exc


@app.post("/api/screener/search")
async def search_screener(request: ScreenerSearchRequest) -> ScreenerSearchResponse:
    return await run_in_threadpool(_search_screener_response, request)


@app.get("/api/user-strategies")
async def list_user_strategies() -> list[UserStrategyResponse]:
    try:
        with SessionLocal() as session:
            rows = session.scalars(
                select(UserStrategy)
                .where(UserStrategy.is_active.is_(True))
                .order_by(UserStrategy.created_at.desc(), UserStrategy.id.desc())
            ).all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"사용자 전략 DB 연결 확인 필요: {exc.__class__.__name__}",
        ) from exc

    return [_user_strategy_response(row) for row in rows]


@app.post("/api/user-strategies", status_code=201)
async def create_user_strategy(request: UserStrategyCreate) -> UserStrategyResponse:
    normalized = _normalize_user_strategy_create(request)

    try:
        with SessionLocal() as session:
            strategy = UserStrategy(
                code=f"user-{uuid4().hex[:12]}",
                name=normalized.name,
                summary=normalized.summary,
                formula=normalized.formula,
                result_count=normalized.result_count,
            )
            session.add(strategy)
            session.commit()
            session.refresh(strategy)
            return _user_strategy_response(strategy)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"사용자 전략 DB 저장 실패: {exc.__class__.__name__}",
        ) from exc


@app.delete("/api/user-strategies/{strategy_code}")
async def delete_user_strategy(strategy_code: str) -> dict[str, bool]:
    try:
        with SessionLocal() as session:
            strategy = session.scalar(
                select(UserStrategy).where(
                    UserStrategy.code == strategy_code,
                    UserStrategy.is_active.is_(True),
                )
            )
            if strategy is None:
                raise HTTPException(status_code=404, detail="사용자 전략을 찾지 못했습니다.")

            strategy.is_active = False
            session.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"사용자 전략 DB 삭제 실패: {exc.__class__.__name__}",
        ) from exc

    return {"deleted": True}


@app.get("/api/recommendations")
async def list_recommendations() -> list[Recommendation]:
    return RECOMMENDATIONS


@app.get("/api/backtests/preview")
async def backtest_preview() -> BacktestPreview:
    return BACKTEST


@app.post("/api/backtests/run")
async def run_backtest(request: BacktestRunRequest) -> BacktestRunResponse:
    strategy = _find_system_strategy(request.strategy_code)
    strategy_name = strategy.name if strategy else ""
    candidate_formula = None

    if strategy is None and request.strategy_code.startswith("user-"):
        user_strategy = _load_active_user_strategy(request.strategy_code)
        strategy_name = user_strategy.name if user_strategy else ""
        candidate_formula = user_strategy.formula if user_strategy else None

    if not strategy_name:
        raise HTTPException(status_code=404, detail="전략을 찾지 못했습니다.")

    backtest_parameters = _backtest_parameter_overrides_from_request(request)
    result = _build_daily_price_backtest_if_available(
        strategy_code=request.strategy_code,
        strategy_name=strategy_name,
        start_year=request.start_year,
        end_year=request.end_year,
        initial_amount=request.initial_amount,
        candidate_formula=candidate_formula,
        backtest_parameters=backtest_parameters,
    ) or build_sample_backtest(
        strategy_code=request.strategy_code,
        strategy_name=strategy_name,
        start_year=request.start_year,
        end_year=request.end_year,
        initial_amount=request.initial_amount,
        backtest_parameters=backtest_parameters,
    )
    _attach_benchmark_curve(result=result, request=request)
    result["run_id"] = _save_backtest_run(result=result, request=request)

    return BacktestRunResponse(**result)


@app.get("/api/backtests/runs")
async def list_backtest_runs(limit: int = 10) -> list[BacktestRunSummary]:
    safe_limit = max(1, min(limit, 50))

    try:
        with SessionLocal() as session:
            runs = session.scalars(
                select(BacktestRun)
                .order_by(BacktestRun.created_at.desc(), BacktestRun.id.desc())
                .limit(safe_limit)
            ).all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"백테스트 결과 DB 조회 실패: {exc.__class__.__name__}",
        ) from exc

    return [_backtest_summary(run) for run in runs]


@app.get("/api/backtests/runs/{run_id}")
async def get_backtest_run(run_id: int) -> BacktestRunResponse:
    try:
        with SessionLocal() as session:
            run = session.get(BacktestRun, run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="백테스트 결과를 찾지 못했습니다.")

            return _saved_backtest_response(run)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"백테스트 결과 DB 조회 실패: {exc.__class__.__name__}",
        ) from exc


@app.get("/api/dashboard")
async def dashboard(
    include_performance: bool = False,
    refresh_performance: bool = False,
) -> DashboardResponse:
    if refresh_performance:
        STRATEGY_PERFORMANCE_CACHE["key"] = None
        STRATEGY_PERFORMANCE_CACHE["strategies"] = None
    strategies = _strategies_with_performance() if include_performance else STRATEGIES

    return DashboardResponse(
        as_of=today_kst(),
        modes=[
            {"code": AppMode.RESEARCH.value, "label": "리서치", "enabled": True},
            {"code": AppMode.LIVE_READONLY.value, "label": "실계좌 읽기", "enabled": False},
            {"code": AppMode.LIVE_TRADING.value, "label": "실거래", "enabled": _env_bool("LIVE_TRADING_ENABLED")},
        ],
        strategies=strategies,
        recommendations=RECOMMENDATIONS,
        backtest=BACKTEST,
    )


@app.get("/api/strategies/performance")
async def strategy_performance(refresh: bool = False) -> list[StrategyPerformanceResponse]:
    if refresh:
        STRATEGY_PERFORMANCE_CACHE["key"] = None
        STRATEGY_PERFORMANCE_CACHE["strategies"] = None

    return [
        StrategyPerformanceResponse(strategy_code=strategy.code, performance=strategy.performance)
        for strategy in _strategies_with_performance()
        if strategy.performance is not None
    ]


@app.get("/api/data/status")
async def data_status() -> DataStatusResponse:
    provider_status = provider_status_rows()

    try:
        with SessionLocal() as session:
            table_counts = {
                "markets": session.scalar(select(func.count()).select_from(Market)) or 0,
                "instruments": session.scalar(select(func.count()).select_from(Instrument)) or 0,
                "daily_prices": session.scalar(select(func.count()).select_from(DailyPrice)) or 0,
                "quote_snapshots": session.scalar(select(func.count()).select_from(QuoteSnapshot)) or 0,
                "supply_flow_dailies": session.scalar(select(func.count()).select_from(SupplyFlowDaily)) or 0,
                "risk_indicator_dailies": session.scalar(select(func.count()).select_from(RiskIndicatorDaily)) or 0,
                "fundamental_ratios": session.scalar(select(func.count()).select_from(FundamentalRatio)) or 0,
                "broker_audit_logs": session.scalar(select(func.count()).select_from(BrokerAuditLog)) or 0,
                "data_import_jobs": session.scalar(select(func.count()).select_from(DataImportJob)) or 0,
                "user_strategies": session.scalar(select(func.count()).select_from(UserStrategy)) or 0,
                "backtest_runs": session.scalar(select(func.count()).select_from(BacktestRun)) or 0,
                "strategy_selection_runs": session.scalar(select(func.count()).select_from(StrategySelectionRun))
                or 0,
            }
    except SQLAlchemyError as exc:
        return DataStatusResponse(
            connected=False,
            provider_status=provider_status,
            table_counts={},
            message=f"DB 연결 확인 필요: {exc.__class__.__name__}",
        )

    return DataStatusResponse(
        connected=True,
        provider_status=provider_status,
        table_counts=table_counts,
        message="로컬 MySQL 연결 정상",
    )


@app.post("/api/data/manual-refresh", status_code=202)
async def start_manual_data_refresh(request: ManualDataRefreshRequest) -> ManualDataRefreshJobResponse:
    job_id = uuid4().hex
    job = {
        "job_id": job_id,
        "status": "queued",
        "stage": "대기 중",
        "progress_pct": 0,
        "current_step": 0,
        "total_steps": 0,
        "success_count": 0,
        "failed_count": 0,
        "saved_count": 0,
        "started_at": now_kst_naive(),
        "finished_at": None,
        "expected_daily_price_date": _expected_latest_daily_price_date(),
        "latest_daily_price_date": _latest_daily_price_date(),
        "message": "최신 데이터 갱신 작업을 시작합니다.",
        "warnings": [],
    }
    with MANUAL_DATA_REFRESH_LOCK:
        MANUAL_DATA_REFRESH_JOBS[job_id] = job

    thread = threading.Thread(target=_run_manual_data_refresh, args=(job_id, request), daemon=True)
    thread.start()
    return _manual_refresh_job_response(job)


@app.get("/api/data/manual-refresh/{job_id}")
async def get_manual_data_refresh(job_id: str) -> ManualDataRefreshJobResponse:
    job = _get_manual_refresh_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="데이터 갱신 작업을 찾을 수 없습니다.")
    return _manual_refresh_job_response(job)


@app.get("/api/data/quality")
async def data_quality() -> DataQualityResponse:
    provider_priority = tuple(_daily_price_provider_priority())

    try:
        with SessionLocal() as session:
            instrument_count = session.scalar(select(func.count()).select_from(Instrument)) or 0
            daily_price_count = session.scalar(select(func.count()).select_from(DailyPrice)) or 0
            latest_trade_date = session.scalar(select(func.max(DailyPrice.trade_date)))
            provider_rows = session.execute(
                select(DailyPrice.provider, func.count(DailyPrice.id))
                .group_by(DailyPrice.provider)
                .order_by(DailyPrice.provider)
            ).all()
            covered_symbol_count = (
                session.scalar(
                    select(func.count()).select_from(
                        select(DailyPrice.instrument_id)
                        .where(
                            DailyPrice.provider.in_(provider_priority),
                            DailyPrice.is_adjusted.is_(False),
                        )
                        .group_by(DailyPrice.instrument_id)
                        .having(func.count(DailyPrice.id) >= 20)
                        .subquery()
                    )
                )
                or 0
            )
            invalid_ohlcv_count = (
                session.scalar(
                    select(func.count())
                    .select_from(DailyPrice)
                    .where(
                        or_(
                            DailyPrice.close_price <= 0,
                            DailyPrice.high_price < DailyPrice.low_price,
                            DailyPrice.open_price < DailyPrice.low_price,
                            DailyPrice.open_price > DailyPrice.high_price,
                            DailyPrice.close_price < DailyPrice.low_price,
                            DailyPrice.close_price > DailyPrice.high_price,
                            DailyPrice.volume < 0,
                            DailyPrice.trading_value < 0,
                        )
                    )
                )
                or 0
            )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"데이터 품질 검사 DB 조회 실패: {exc.__class__.__name__}",
        ) from exc

    checks: list[DataQualityCheck] = []
    checks.append(
        _quality_check(
            code="instrument-universe",
            label="종목 유니버스",
            status="ok" if instrument_count >= 50 else "warning" if instrument_count > 0 else "error",
            value=f"{instrument_count:,}개",
            message=(
                "전략 후보를 넓게 찾을 수 있는 종목 수입니다."
                if instrument_count >= 50
                else "초기 후보군은 동작하지만 전체 시장 검색에는 종목 적재가 더 필요합니다."
                if instrument_count > 0
                else "종목 목록이 비어 있습니다."
            ),
        )
    )
    checks.append(
        _quality_check(
            code="daily-price-count",
            label="일봉 가격 데이터",
            status="ok" if daily_price_count >= 1_000 else "warning" if daily_price_count > 0 else "error",
            value=f"{daily_price_count:,}건",
            message=(
                "전략과 백테스트에 사용할 일봉 데이터가 누적되어 있습니다."
                if daily_price_count >= 1_000
                else "기본 동작은 가능하지만 기간과 종목 범위를 넓히려면 추가 적재가 필요합니다."
                if daily_price_count > 0
                else "일봉 데이터가 없어 실제 데이터 기반 전략 실행이 어렵습니다."
            ),
        )
    )

    if latest_trade_date is None:
        checks.append(
            _quality_check(
                code="daily-price-freshness",
                label="최근 거래일",
                status="error",
                value="없음",
                message="저장된 일봉 거래일이 없습니다.",
            )
        )
    else:
        stale_days = (today_kst() - latest_trade_date).days
        checks.append(
            _quality_check(
                code="daily-price-freshness",
                label="최근 거래일",
                status="ok" if stale_days <= 7 else "warning" if stale_days <= 21 else "error",
                value=f"{latest_trade_date.isoformat()} ({stale_days}일 전)",
                message=(
                    "최근 데이터가 비교적 최신입니다."
                    if stale_days <= 7
                    else "데이터가 다소 오래되었습니다. 전략 실행 전 자동 갱신 여부를 확인하세요."
                    if stale_days <= 21
                    else "데이터가 오래되어 현재 시장 상태 반영이 어렵습니다."
                ),
            )
        )

    checks.append(
        _quality_check(
            code="daily-price-coverage",
            label="종목별 일봉 커버리지",
            status="ok" if covered_symbol_count >= 10 else "warning" if covered_symbol_count > 0 else "error",
            value=f"{covered_symbol_count:,}개 종목",
            message=(
                "전략 후보 최소 수량을 계산할 수 있는 종목별 일봉 길이가 확보되어 있습니다."
                if covered_symbol_count >= 10
                else "일부 종목만 전략 계산에 필요한 최소 일봉 길이를 갖고 있습니다."
                if covered_symbol_count > 0
                else "최소 20개 일봉을 가진 종목이 없습니다."
            ),
        )
    )
    checks.append(
        _quality_check(
            code="ohlcv-validity",
            label="OHLCV 이상값",
            status="ok" if invalid_ohlcv_count == 0 else "error",
            value=f"{invalid_ohlcv_count:,}건",
            message=(
                "가격, 고가/저가, 거래량의 기본 무결성 오류가 없습니다."
                if invalid_ohlcv_count == 0
                else "고가/저가/종가/거래량 중 비정상 값이 있어 정제 또는 재수집이 필요합니다."
            ),
        )
    )
    checks.append(
        _quality_check(
            code="provider-mix",
            label="데이터 제공처",
            status="ok" if provider_rows else "warning",
            value=_provider_counts_label([(str(row[0]), int(row[1])) for row in provider_rows]),
            message=(
                "저장 데이터의 제공처를 추적할 수 있습니다."
                if provider_rows
                else "아직 저장된 제공처별 가격 데이터가 없습니다."
            ),
        )
    )

    return DataQualityResponse(
        generated_at=now_kst_naive(),
        summary_status=_quality_summary_status(checks),
        checks=checks,
    )


@app.get("/api/data/market-calendar")
async def market_calendar(
    market: str = "KR",
    start: date | None = None,
    end: date | None = None,
) -> MarketCalendarResponse:
    effective_end = end or today_kst()
    effective_start = start or (effective_end - timedelta(days=14))

    try:
        payload = market_calendar_range(
            market=market,
            start=effective_start,
            end=effective_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MarketCalendarResponse(
        market=payload["market"],
        timezone=payload["timezone"],
        start=payload["start"],
        end=payload["end"],
        open_days=payload["open_days"],
        closed_days=payload["closed_days"],
        items=[MarketCalendarDayResponse(**item) for item in payload["items"]],
    )


@app.get("/api/data/opendart/corp-codes/status")
async def open_dart_corp_code_status() -> OpenDartCorpCodeCacheStatusResponse:
    return OpenDartCorpCodeCacheStatusResponse(**get_open_dart_corp_code_cache_status())


@app.post("/api/data/opendart/corp-codes/cache", status_code=201)
async def cache_open_dart_corp_codes(force_refresh: bool = False) -> OpenDartCorpCodeCacheResponse:
    try:
        rows = fetch_open_dart_corp_codes(force_refresh=force_refresh)
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    listed_count = sum(1 for row in rows if row.get("stock_code"))
    status = get_open_dart_corp_code_cache_status()

    return OpenDartCorpCodeCacheResponse(
        provider="OpenDART",
        fetched_count=len(rows),
        listed_count=listed_count,
        cache_path=status["cache_path"],
        message=f"OpenDART 고유번호 {len(rows):,}건을 캐시했습니다.",
    )


@app.get("/api/data/opendart/financial-statements")
async def open_dart_financial_statements(
    symbol: str,
    business_year: int,
    report_code: str = "11011",
    fs_div: str = "CFS",
    force_refresh_corp_codes: bool = False,
) -> OpenDartFinancialStatementResponse:
    try:
        items = fetch_open_dart_financial_statements(
            symbol=symbol,
            business_year=business_year,
            report_code=report_code,
            fs_div=fs_div,
            force_refresh_corp_codes=force_refresh_corp_codes,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return OpenDartFinancialStatementResponse(
        provider="OpenDART",
        symbol=symbol.strip().upper(),
        business_year=business_year,
        report_code=report_code.strip(),
        fs_div=fs_div.strip().upper(),
        count=len(items),
        summary=OpenDartFinancialSummaryResponse(**summarize_open_dart_financial_statements(items)),
        items=[OpenDartFinancialStatementItem(**item) for item in items],
    )


@app.post("/api/data/opendart/financial-statements/import")
async def import_open_dart_financial_statements(
    symbol: str,
    business_year: int,
    report_code: str = "11011",
    fs_div: str = "CFS",
    exchange: str = "KOSPI",
    force_refresh_corp_codes: bool = False,
) -> OpenDartFinancialStatementImportResponse:
    try:
        items = fetch_open_dart_financial_statements(
            symbol=symbol,
            business_year=business_year,
            report_code=report_code,
            fs_div=fs_div,
            force_refresh_corp_codes=force_refresh_corp_codes,
        )
        summary = summarize_open_dart_financial_statements(items)
        fallback_name = str(items[0].get("corp_name") or symbol.strip().upper()) if items else symbol.strip().upper()
        with SessionLocal() as session:
            saved_count = _save_open_dart_fundamental_summary(
                session=session,
                symbol=symbol,
                name=fallback_name,
                exchange=exchange,
                business_year=business_year,
                summary=summary,
            )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"OpenDART 재무요약 DB 저장 실패: {exc.__class__.__name__}",
        ) from exc

    return OpenDartFinancialStatementImportResponse(
        provider=OPEN_DART_FUNDAMENTAL_PROVIDER,
        symbol=symbol.strip().upper(),
        business_year=business_year,
        report_code=report_code.strip(),
        fs_div=fs_div.strip().upper(),
        count=len(items),
        saved_count=saved_count,
        summary=OpenDartFinancialSummaryResponse(**summary),
    )


@app.get("/api/data/krx/instruments")
async def krx_instruments(
    market: str = "KOSPI",
    limit: int = 50,
    base_date: str | None = None,
) -> KrxInstrumentPreviewResponse:
    effective_base_date = base_date or default_krx_base_date()

    try:
        instruments = fetch_krx_instruments(
            market=market,
            limit=limit,
            base_date=effective_base_date,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KrxInstrumentPreviewResponse(
        provider="KRX Open API",
        market=market.strip().upper(),
        base_date=effective_base_date,
        count=len(instruments),
        instruments=[KrxInstrumentPreview(**item) for item in instruments],
    )


@app.post("/api/data/krx/instruments/import", status_code=201)
async def import_krx_instruments(
    request: KrxInstrumentImportRequest,
) -> KrxInstrumentImportResponse:
    normalized_market = request.market.strip().upper() or "ALL"
    effective_base_date = request.base_date or default_krx_base_date()

    try:
        instruments = await run_in_threadpool(
            fetch_krx_instruments,
            market=normalized_market,
            limit=request.limit,
            base_date=effective_base_date,
        )
        return await run_in_threadpool(
            _save_krx_instruments,
            market=normalized_market,
            base_date=effective_base_date,
            rows=instruments,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"KRX 종목 목록 저장 중 DB 오류가 발생했습니다: {exc.__class__.__name__}",
        ) from exc


@app.get("/api/data/kis/token/status")
async def kis_token_status() -> KisTokenStatusResponse:
    return KisTokenStatusResponse(**get_kis_token_status())


@app.get("/api/data/kis/websocket/approval/status")
async def kis_websocket_approval_status() -> KisWebSocketApprovalStatusResponse:
    return KisWebSocketApprovalStatusResponse(**get_kis_ws_approval_status())


@app.post("/api/data/kis/websocket/approval-key")
async def issue_kis_websocket_approval_key(
    request: KisWebSocketApprovalIssueRequest,
) -> KisWebSocketApprovalStatusResponse:
    await run_in_threadpool(get_kis_ws_approval_key, force_refresh=request.force_refresh)
    return KisWebSocketApprovalStatusResponse(**get_kis_ws_approval_status())


@app.get("/api/data/kis/realtime/quotes/status")
async def kis_realtime_quote_status() -> KisRealtimeQuoteStatusResponse:
    status = await kis_realtime_quote_service.status()
    return KisRealtimeQuoteStatusResponse(**status.as_response_row())


@app.get("/api/data/kis/realtime/quotes/latest")
async def kis_realtime_latest_quotes() -> list[KisRealtimeQuoteResponse]:
    quotes = await kis_realtime_quote_service.latest_quotes()
    return [KisRealtimeQuoteResponse(**quote.as_response_row()) for quote in quotes]


@app.post("/api/data/kis/realtime/quotes/subscribe")
async def subscribe_kis_realtime_quotes(
    request: KisRealtimeQuoteSubscribeRequest,
) -> KisRealtimeQuoteStatusResponse:
    try:
        status = await kis_realtime_quote_service.subscribe(request.symbols)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KisRealtimeQuoteStatusResponse(**status.as_response_row())


@app.post("/api/data/kis/realtime/quotes/unsubscribe")
async def unsubscribe_kis_realtime_quotes(
    request: KisRealtimeQuoteSubscribeRequest,
) -> KisRealtimeQuoteStatusResponse:
    try:
        status = await kis_realtime_quote_service.unsubscribe(request.symbols)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KisRealtimeQuoteStatusResponse(**status.as_response_row())


@app.post("/api/data/kis/realtime/quotes/stop")
async def stop_kis_realtime_quotes() -> KisRealtimeQuoteStatusResponse:
    status = await kis_realtime_quote_service.stop()
    return KisRealtimeQuoteStatusResponse(**status.as_response_row())


@app.get("/api/broker/kis/account/status")
async def kis_broker_account_status() -> KisBrokerAccountStatusResponse:
    api_ready = is_kis_open_api_ready()
    account_configured = has_kis_account_credentials()
    paper_mode = is_kis_paper_trading()
    ready = api_ready and account_configured
    if not api_ready:
        message = "KIS App Key/Secret 설정이 필요합니다."
    elif not account_configured:
        message = "KIS 계좌번호와 계좌상품코드 설정이 필요합니다."
    elif paper_mode:
        message = "KIS 모의투자 계좌 읽기 준비가 완료되었습니다."
    else:
        message = "KIS 실전 계좌 읽기 설정입니다. 실거래 주문은 기본 비활성화 상태입니다."

    return KisBrokerAccountStatusResponse(
        provider="KIS Open API",
        ready=ready,
        environment=get_kis_environment_name(),
        account_configured=account_configured,
        account_label=_masked_kis_account_label(),
        paper_trading_enabled=_paper_trading_enabled(),
        live_trading_enabled=_live_trading_enabled(),
        message=message,
    )


@app.get("/api/broker/kis/safety-status")
async def kis_trading_safety_status() -> KisTradingSafetyStatusResponse:
    return _trading_safety_status_response()


@app.get("/api/broker/kis/balance")
async def kis_broker_balance() -> KisBrokerBalanceResponse:
    request_payload = {
        "account_label": _masked_kis_account_label(),
        "environment": get_kis_environment_name(),
        "mode": "read-only",
    }
    try:
        result = await run_in_threadpool(fetch_kis_domestic_balance)
        _try_create_broker_audit_log(
            action="account_balance.read",
            status="success",
            request_payload=request_payload,
            response_payload={
                "holding_count": len(result.get("holdings", [])),
                "summary": result.get("summary", {}),
            },
            message="KIS 잔고 조회 성공",
        )
    except MarketDataProviderUnavailable as exc:
        _try_create_broker_audit_log(
            action="account_balance.read",
            status="failed",
            request_payload=request_payload,
            response_payload={},
            message=str(exc),
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KisBrokerBalanceResponse(**result)


@app.get("/api/broker/kis/buyable-cash")
async def kis_broker_buyable_cash(
    symbol: str,
    order_price: int = 0,
    order_type: str = "market",
) -> KisBuyableCashResponse:
    request_payload = {
        "account_label": _masked_kis_account_label(),
        "environment": get_kis_environment_name(),
        "symbol": symbol,
        "order_price": order_price,
        "order_type": order_type,
    }
    try:
        result = await run_in_threadpool(
            fetch_kis_buyable_cash,
            symbol=symbol,
            order_price=order_price,
            order_type=order_type,
        )
        _try_create_broker_audit_log(
            action="buyable_cash.read",
            status="success",
            request_payload=request_payload,
            response_payload={
                "symbol": result.get("symbol", symbol),
                "cash_buy_amount": result.get("cash_buy_amount", 0),
                "cash_buy_quantity": result.get("cash_buy_quantity", 0),
            },
            message="KIS 매수가능금액 조회 성공",
        )
    except MarketDataProviderUnavailable as exc:
        _try_create_broker_audit_log(
            action="buyable_cash.read",
            status="failed",
            request_payload=request_payload,
            response_payload={},
            message=str(exc),
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KisBuyableCashResponse(**result)


@app.get("/api/broker/kis/orders")
async def kis_broker_orders(
    start: date | None = None,
    end: date | None = None,
    side: str = "all",
    execution_status: str = "all",
    symbol: str = "",
) -> KisOrderExecutionResponse:
    request_payload = {
        "account_label": _masked_kis_account_label(),
        "environment": get_kis_environment_name(),
        "start": start,
        "end": end,
        "side": side,
        "execution_status": execution_status,
        "symbol": symbol,
        "mode": "read-only",
    }
    try:
        result = await run_in_threadpool(
            fetch_kis_daily_order_executions,
            start=start,
            end=end,
            side=side,
            execution_status=execution_status,
            symbol=symbol,
        )
        _try_create_broker_audit_log(
            action="order_history.read",
            status="success",
            request_payload=request_payload,
            response_payload={
                "order_count": len(result.get("orders", [])),
                "summary": result.get("summary", {}),
            },
            message="KIS 주문체결 내역 조회 성공",
        )
    except MarketDataProviderUnavailable as exc:
        _try_create_broker_audit_log(
            action="order_history.read",
            status="failed",
            request_payload=request_payload,
            response_payload={},
            message=str(exc),
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KisOrderExecutionResponse(**result)


@app.post("/api/broker/kis/order-proposals")
async def kis_order_proposal(request: KisOrderProposalRequest) -> KisOrderProposalResponse:
    strategy_response = await strategy_candidates(request.strategy_code, limit=request.max_positions)
    available_cash, cash_verified, warnings = await run_in_threadpool(_proposal_available_cash)
    remaining_slots, slot_warnings = _remaining_daily_paper_order_slots()
    warnings.extend(slot_warnings)

    if _emergency_stop_enabled():
        warnings.append("긴급 중지 상태라 주문 제출은 차단되며, 제안만 생성합니다.")
    if not is_kis_paper_trading():
        warnings.append("현재 KIS 실전 계좌 설정입니다. 이 화면에서는 주문 제안만 생성합니다.")
    elif not _paper_trading_enabled():
        warnings.append("PAPER_TRADING_ENABLED=false 상태라 모의주문 제출은 잠겨 있습니다.")
    if remaining_slots == 0:
        warnings.append("오늘 남은 모의주문 가능 횟수가 없습니다.")
    if not strategy_response.candidates:
        warnings.append("선택한 전략의 후보 종목이 없습니다.")

    lines, total_estimated_amount, executable_count, line_warnings = _build_kis_order_proposal_lines(
        candidates=strategy_response.candidates,
        request=request,
        available_cash=available_cash,
        cash_verified=cash_verified,
        remaining_daily_slots=remaining_slots,
    )
    warnings.extend(line_warnings)

    cash_buffer_amount = int(available_cash * request.cash_buffer_rate / 100) if cash_verified else 0
    response = KisOrderProposalResponse(
        provider="KIS Open API",
        environment=get_kis_environment_name(),
        account_label=_masked_kis_account_label(),
        proposal_id=uuid4().hex[:12],
        generated_at=now_kst_naive().isoformat(timespec="seconds"),
        strategy_code=strategy_response.strategy_code,
        strategy_name=strategy_response.strategy_name,
        source=strategy_response.source,
        max_positions=request.max_positions,
        amount_per_symbol=request.amount_per_symbol,
        order_type=request.order_type,
        cash_buffer_rate=request.cash_buffer_rate,
        available_cash=available_cash,
        cash_buffer_amount=cash_buffer_amount,
        total_estimated_amount=total_estimated_amount,
        executable_count=executable_count,
        warnings=warnings,
        lines=lines,
    )
    audit_log_id = _try_create_broker_audit_log(
        action="order_proposal.create",
        status="success",
        request_payload={
            "account_label": _masked_kis_account_label(),
            "environment": get_kis_environment_name(),
            "strategy_code": request.strategy_code,
            "max_positions": request.max_positions,
            "amount_per_symbol": request.amount_per_symbol,
            "order_type": request.order_type,
            "cash_buffer_rate": request.cash_buffer_rate,
        },
        response_payload={
            "proposal_id": response.proposal_id,
            "strategy_code": response.strategy_code,
            "line_count": len(response.lines),
            "executable_count": response.executable_count,
            "total_estimated_amount": response.total_estimated_amount,
            "warning_count": len(response.warnings),
        },
        message="KIS 전략 주문 제안 생성",
    )
    response.audit_log_id = audit_log_id
    return response


@app.post("/api/broker/kis/paper/orders/batch", status_code=202)
async def kis_paper_batch_order(request: KisPaperBatchOrderRequest) -> KisPaperBatchOrderResponse:
    if not is_kis_paper_trading():
        raise HTTPException(status_code=403, detail="현재 KIS_IS_PAPER=true인 모의투자 설정에서만 사용할 수 있습니다.")
    if not _paper_trading_enabled():
        raise HTTPException(status_code=403, detail="PAPER_TRADING_ENABLED=true 설정 후 사용할 수 있습니다.")
    if _emergency_stop_enabled():
        raise HTTPException(status_code=423, detail="EMERGENCY_STOP_ENABLED=true 상태라 주문 제출을 차단했습니다.")
    if not request.confirm_submit:
        raise HTTPException(status_code=400, detail="confirm_submit=true가 있어야 모의주문을 제출합니다.")
    if _manual_order_confirmation_required() and request.confirm_phrase.strip() != "모의주문 실행":
        raise HTTPException(status_code=400, detail="확인 문구가 일치해야 모의 일괄 주문을 제출합니다.")

    batch_id = uuid4().hex[:12]
    request_payload = {
        "account_label": _masked_kis_account_label(),
        "environment": get_kis_environment_name(),
        "batch_id": batch_id,
        "order_count": len(request.orders),
        "orders": [
            {
                "side": order.side,
                "symbol": order.symbol,
                "name": order.name,
                "quantity": order.quantity,
                "order_type": order.order_type,
                "price": order.price,
                "exchange_id": order.exchange_id,
            }
            for order in request.orders
        ],
    }
    try:
        daily_loss_amount = _validate_daily_loss_stop()
        if daily_loss_amount:
            request_payload["daily_loss_amount"] = daily_loss_amount
    except HTTPException as exc:
        _try_create_broker_audit_log(
            action="paper_batch_order.daily_loss_stop",
            status="failed",
            request_payload=request_payload,
            response_payload={"detail": exc.detail},
            message=str(exc.detail),
        )
        raise

    try:
        estimated_orders = _validate_paper_batch_order_risk_limits(request.orders)
    except HTTPException as exc:
        _try_create_broker_audit_log(
            action="paper_batch_order.risk_check",
            status="failed",
            request_payload=request_payload,
            response_payload={"detail": exc.detail},
            message=str(exc.detail),
        )
        raise
    except MarketDataProviderUnavailable as exc:
        _try_create_broker_audit_log(
            action="paper_batch_order.risk_check",
            status="failed",
            request_payload=request_payload,
            response_payload={},
            message=str(exc),
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    total_estimated_amount = sum(amount for _order, amount in estimated_orders)
    try:
        before_log_id = _create_broker_audit_log(
            action="paper_batch_order.submit.before",
            status="pending",
            request_payload={**request_payload, "total_estimated_amount": total_estimated_amount},
            response_payload={},
            message="KIS 모의 일괄 주문 제출 전 로그",
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"주문 감사 로그 저장 실패로 일괄 주문을 제출하지 않았습니다: {exc.__class__.__name__}",
        ) from exc

    results: list[KisPaperBatchOrderResult] = []
    for order, estimated_amount in estimated_orders:
        try:
            result = submit_kis_domestic_cash_order(
                side=order.side,
                symbol=order.symbol,
                quantity=order.quantity,
                order_type=order.order_type,
                price=order.price,
                exchange_id=order.exchange_id,
            )
            results.append(
                KisPaperBatchOrderResult(
                    symbol=order.symbol,
                    name=order.name,
                    side=order.side,
                    order_type=order.order_type,
                    quantity=order.quantity,
                    price=int(result.get("price") or order.price),
                    estimated_amount=estimated_amount,
                    status="success",
                    order_no=str(result.get("order_no", "")),
                    order_time=str(result.get("order_time", "")),
                    message=str(result.get("message", "모의주문 접수")),
                )
            )
        except (MarketDataProviderUnavailable, ValueError) as exc:
            results.append(
                KisPaperBatchOrderResult(
                    symbol=order.symbol,
                    name=order.name,
                    side=order.side,
                    order_type=order.order_type,
                    quantity=order.quantity,
                    price=order.price,
                    estimated_amount=estimated_amount,
                    status="failed",
                    message=str(exc),
                )
            )
            break

    submitted_count = sum(1 for result in results if result.status == "success")
    failed_count = len(results) - submitted_count
    batch_status = "success" if failed_count == 0 and submitted_count == len(request.orders) else "partial_failed"
    response = KisPaperBatchOrderResponse(
        provider="KIS Open API",
        environment=get_kis_environment_name(),
        account_label=_masked_kis_account_label(),
        batch_id=batch_id,
        submitted_count=submitted_count,
        failed_count=failed_count,
        total_estimated_amount=total_estimated_amount,
        status=batch_status,
        results=results,
        before_audit_log_id=before_log_id,
    )
    after_log_id = _try_create_broker_audit_log(
        action="paper_batch_order.submit.after",
        status=batch_status,
        request_payload={**request_payload, "before_audit_log_id": before_log_id},
        response_payload={
            "batch_id": batch_id,
            "submitted_count": submitted_count,
            "failed_count": failed_count,
            "total_estimated_amount": total_estimated_amount,
            "results": [result.model_dump() for result in results],
        },
        message="KIS 모의 일괄 주문 제출 결과",
    )
    response.after_audit_log_id = after_log_id
    return response


@app.post("/api/broker/kis/paper/orders", status_code=202)
async def kis_paper_order(request: KisPaperOrderRequest) -> KisPaperOrderResponse:
    if not is_kis_paper_trading():
        raise HTTPException(status_code=403, detail="현재 KIS_IS_PAPER=true인 모의투자 설정에서만 사용할 수 있습니다.")
    if not _paper_trading_enabled():
        raise HTTPException(status_code=403, detail="PAPER_TRADING_ENABLED=true 설정 후 사용할 수 있습니다.")
    if _emergency_stop_enabled():
        raise HTTPException(status_code=423, detail="EMERGENCY_STOP_ENABLED=true 상태라 주문 제출을 차단했습니다.")
    if not request.confirm_submit:
        raise HTTPException(status_code=400, detail="confirm_submit=true가 있어야 모의주문을 제출합니다.")
    if _manual_order_confirmation_required() and request.confirm_phrase.strip() != "모의주문 실행":
        raise HTTPException(status_code=400, detail="확인 문구가 일치해야 모의주문을 제출합니다.")

    request_payload = {
        "account_label": _masked_kis_account_label(),
        "environment": get_kis_environment_name(),
        "side": request.side,
        "symbol": request.symbol,
        "quantity": request.quantity,
        "order_type": request.order_type,
        "price": request.price,
        "exchange_id": request.exchange_id,
    }
    try:
        daily_loss_amount = _validate_daily_loss_stop()
        if daily_loss_amount:
            request_payload["daily_loss_amount"] = daily_loss_amount
    except HTTPException as exc:
        _try_create_broker_audit_log(
            action="paper_order.daily_loss_stop",
            status="failed",
            request_payload=request_payload,
            response_payload={"detail": exc.detail},
            message=str(exc.detail),
        )
        raise

    try:
        estimated_amount = _validate_paper_order_risk_limits(request)
        request_payload["estimated_amount"] = estimated_amount
    except HTTPException as exc:
        _try_create_broker_audit_log(
            action="paper_order.risk_check",
            status="failed",
            request_payload=request_payload,
            response_payload={"detail": exc.detail},
            message=str(exc.detail),
        )
        raise
    except MarketDataProviderUnavailable as exc:
        _try_create_broker_audit_log(
            action="paper_order.risk_check",
            status="failed",
            request_payload=request_payload,
            response_payload={},
            message=str(exc),
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        pre_log_id = _create_broker_audit_log(
            action="paper_order.submit.before",
            status="pending",
            request_payload=request_payload,
            response_payload={},
            message="KIS 모의주문 제출 전 로그",
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"주문 감사 로그 저장 실패로 주문을 제출하지 않았습니다: {exc.__class__.__name__}",
        ) from exc

    try:
        result = submit_kis_domestic_cash_order(
            side=request.side,
            symbol=request.symbol,
            quantity=request.quantity,
            order_type=request.order_type,
            price=request.price,
            exchange_id=request.exchange_id,
        )
        after_log_id = _create_broker_audit_log(
            action="paper_order.submit.after",
            status="success",
            request_payload={**request_payload, "pre_audit_log_id": pre_log_id},
            response_payload={
                "order_no": result.get("order_no", ""),
                "order_time": result.get("order_time", ""),
                "message": result.get("message", ""),
            },
            message="KIS 모의주문 제출 성공",
        )
    except MarketDataProviderUnavailable as exc:
        _try_create_broker_audit_log(
            action="paper_order.submit.after",
            status="failed",
            request_payload={**request_payload, "pre_audit_log_id": pre_log_id},
            response_payload={},
            message=str(exc),
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        _try_create_broker_audit_log(
            action="paper_order.submit.after",
            status="failed",
            request_payload={**request_payload, "pre_audit_log_id": pre_log_id},
            response_payload={},
            message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KisPaperOrderResponse(**result, audit_log_id=after_log_id)


@app.get("/api/data/kis/current-price")
async def kis_current_price(symbol: str) -> KisCurrentPriceResponse:
    try:
        price = fetch_kis_current_price(symbol=symbol)
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KisCurrentPriceResponse(**price)


@app.get("/api/data/kis/market-cap-ranking")
async def kis_market_cap_ranking(
    market: str = "ALL",
    limit: int = 50,
) -> KisMarketCapRankingResponse:
    safe_limit = max(1, min(limit, 100))

    try:
        items = fetch_kis_market_cap_ranking(limit=safe_limit, market=market)
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KisMarketCapRankingResponse(
        provider="KIS Open API",
        count=len(items),
        items=[KisMarketCapRankingItem(**item) for item in items],
    )


@app.post("/api/data/kis/instruments/import", status_code=201)
async def import_kis_instruments_from_market_cap_ranking(
    request: KisInstrumentImportRequest,
) -> KisInstrumentImportResponse:
    normalized_market = request.market.strip().upper() or "ALL"

    try:
        rows = await run_in_threadpool(
            fetch_kis_market_cap_ranking,
            limit=request.limit,
            market=normalized_market,
        )
        return await run_in_threadpool(
            _save_kis_instruments_from_market_cap_ranking,
            market=normalized_market,
            rows=rows,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"KIS 종목 목록 DB 저장 실패: {exc.__class__.__name__}",
        ) from exc


@app.get("/api/data/kis/investor-trade-daily")
async def kis_investor_trade_daily(
    symbol: str,
    base_date: date | None = None,
    limit: int = 30,
) -> KisInvestorTradeDailyResponse:
    safe_limit = max(1, min(limit, 100))

    try:
        items = fetch_kis_investor_trade_daily(
            symbol=symbol,
            base_date=base_date,
            limit=safe_limit,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KisInvestorTradeDailyResponse(
        provider="KIS Open API",
        symbol=symbol.strip().upper(),
        count=len(items),
        items=[KisInvestorTradeDailyItem(**item) for item in items],
    )


@app.get("/api/data/kis/daily-short-sale")
async def kis_daily_short_sale(
    symbol: str,
    start: date | None = None,
    end: date | None = None,
    limit: int = 30,
) -> KisDailyShortSaleResponse:
    safe_limit = max(1, min(limit, 100))

    try:
        items = fetch_kis_daily_short_sale(
            symbol=symbol,
            start=start,
            end=end,
            limit=safe_limit,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KisDailyShortSaleResponse(
        provider="KIS Open API",
        symbol=symbol.strip().upper(),
        count=len(items),
        items=[KisDailyShortSaleItem(**item) for item in items],
    )


@app.get("/api/data/kis/daily-credit-balance")
async def kis_daily_credit_balance(
    symbol: str,
    base_date: date | None = None,
    limit: int = 30,
) -> KisDailyCreditBalanceResponse:
    safe_limit = max(1, min(limit, 100))

    try:
        items = fetch_kis_daily_credit_balance(
            symbol=symbol,
            base_date=base_date,
            limit=safe_limit,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KisDailyCreditBalanceResponse(
        provider="KIS Open API",
        symbol=symbol.strip().upper(),
        count=len(items),
        items=[KisDailyCreditBalanceItem(**item) for item in items],
    )


@app.get("/api/data/kis/financial-ratios")
async def kis_financial_ratios(
    symbol: str,
    period_type: str = "annual",
    limit: int = 8,
) -> KisFinancialRatioResponse:
    safe_limit = max(1, min(limit, 20))

    try:
        items = fetch_kis_financial_ratios(
            symbol=symbol,
            period_type=period_type,
            limit=safe_limit,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    normalized_period_type = "quarter" if period_type.strip().lower() in {"quarter", "quarterly"} else "annual"
    return KisFinancialRatioResponse(
        provider="KIS Open API",
        symbol=symbol.strip().upper(),
        period_type=normalized_period_type,
        count=len(items),
        items=[KisFinancialRatioItem(**item) for item in items],
    )


@app.get("/api/data/krx/daily-prices")
async def krx_daily_prices(
    symbol: str,
    exchange: str = "KOSPI",
    start: date | None = None,
    end: date | None = None,
    limit: int = 120,
) -> KrxDailyPricePreviewResponse:
    safe_limit = max(1, min(limit, 500))

    try:
        prices = fetch_krx_daily_prices(symbol=symbol, exchange=exchange, start=start, end=end)
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    limited_prices = sorted(prices, key=lambda item: str(item["trade_date"]))[-safe_limit:]

    return KrxDailyPricePreviewResponse(
        provider="KRX Open API",
        symbol=symbol.strip().upper(),
        exchange=exchange.strip().upper(),
        count=len(limited_prices),
        prices=[YahooDailyPrice(**item) for item in limited_prices],
    )


@app.post("/api/data/krx/daily-prices/import", status_code=201)
async def import_krx_daily_prices(
    request: KrxDailyPriceImportRequest,
) -> KrxDailyPriceImportResponse:
    try:
        prices = fetch_krx_daily_prices(
            symbol=request.symbol,
            exchange=request.exchange,
            start=request.start,
            end=request.end,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not prices:
        raise HTTPException(status_code=404, detail="KRX 일봉 데이터가 없습니다.")

    try:
        with SessionLocal() as session:
            response = _save_krx_daily_prices(session=session, request=request, prices=prices)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"KRX 일봉 DB 저장 실패: {exc.__class__.__name__}",
        ) from exc

    return response


@app.post("/api/data/krx/daily-prices/import/market", status_code=201)
async def import_krx_market_daily_prices(
    request: KrxMarketDailyPriceImportRequest,
) -> KrxMarketDailyPriceImportResponse:
    try:
        prices = await run_in_threadpool(
            fetch_krx_market_daily_prices,
            market=request.market,
            start=request.start,
            end=request.end,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not prices:
        raise HTTPException(status_code=404, detail="KRX 시장 일봉 데이터가 없습니다.")

    try:
        with SessionLocal() as session:
            response = _save_krx_market_daily_prices(session=session, request=request, prices=prices)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"KRX 시장 일봉 DB 저장 실패: {exc.__class__.__name__}",
        ) from exc

    return response


@app.post("/api/data/krx/daily-prices/import/strategy", status_code=201)
async def import_krx_daily_prices_for_strategy(
    request: KrxDailyPriceBatchImportRequest,
) -> KrxDailyPriceBatchImportResponse:
    strategy = _find_system_strategy(request.strategy_code)
    user_strategy = None

    if strategy is None and request.strategy_code.startswith("user-"):
        user_strategy = _load_active_user_strategy(request.strategy_code)

    if strategy is None and user_strategy is None:
        raise HTTPException(status_code=404, detail="전략을 찾지 못했습니다.")

    return _import_krx_daily_prices_for_strategy_candidates(request)


def _import_krx_daily_prices_for_strategy_candidates(
    request: KrxDailyPriceBatchImportRequest,
) -> KrxDailyPriceBatchImportResponse:
    candidates = _seed_candidates_for_strategy(request.strategy_code, limit=request.max_symbols)
    items: list[KrxDailyPriceBatchImportItem] = []

    for candidate in candidates:
        import_request = KrxDailyPriceImportRequest(
            symbol=str(candidate["symbol"]),
            name=str(candidate["name"]),
            exchange=str(candidate["exchange"]),
            start=request.start,
            end=request.end,
        )

        try:
            prices = fetch_krx_daily_prices(
                symbol=import_request.symbol,
                exchange=import_request.exchange,
                start=import_request.start,
                end=import_request.end,
            )

            if not prices:
                items.append(
                    KrxDailyPriceBatchImportItem(
                        symbol=import_request.symbol,
                        name=import_request.name or import_request.symbol,
                        exchange=import_request.exchange,
                        status="failed",
                        saved_count=0,
                        message="KRX 일봉 데이터 없음",
                    )
                )
                continue

            with SessionLocal() as session:
                saved = _save_krx_daily_prices(
                    session=session,
                    request=import_request,
                    prices=prices,
                )

            items.append(
                KrxDailyPriceBatchImportItem(
                    symbol=saved.symbol,
                    name=import_request.name or saved.symbol,
                    exchange=saved.exchange,
                    status="completed",
                    saved_count=saved.saved_count,
                    message=saved.message,
                )
            )
        except (MarketDataProviderUnavailable, SQLAlchemyError, ValueError) as exc:
            items.append(
                KrxDailyPriceBatchImportItem(
                    symbol=import_request.symbol,
                    name=import_request.name or import_request.symbol,
                    exchange=import_request.exchange,
                    status="failed",
                    saved_count=0,
                    message=str(exc),
                )
            )

    success_count = sum(1 for item in items if item.status == "completed")
    saved_count = sum(item.saved_count for item in items)

    return KrxDailyPriceBatchImportResponse(
        provider="KRX Open API",
        strategy_code=request.strategy_code,
        requested_symbols=len(candidates),
        success_count=success_count,
        failed_count=len(items) - success_count,
        saved_count=saved_count,
        items=items,
    )


@app.get("/api/data/kis/daily-prices")
async def kis_daily_prices(
    symbol: str,
    start: date | None = None,
    end: date | None = None,
    is_adjusted: bool = False,
    limit: int = 120,
) -> KisDailyPricePreviewResponse:
    safe_limit = max(1, min(limit, 500))

    try:
        prices = fetch_kis_daily_prices(
            symbol=symbol,
            start=start,
            end=end,
            is_adjusted=is_adjusted,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    limited_prices = sorted(prices, key=lambda item: str(item["trade_date"]))[-safe_limit:]

    return KisDailyPricePreviewResponse(
        provider="KIS Open API",
        symbol=symbol.strip().upper(),
        count=len(limited_prices),
        prices=[YahooDailyPrice(**item) for item in limited_prices],
    )


@app.post("/api/data/kis/daily-prices/import", status_code=201)
async def import_kis_daily_prices(
    request: KisDailyPriceImportRequest,
) -> KisDailyPriceImportResponse:
    try:
        prices = fetch_kis_daily_prices(
            symbol=request.symbol,
            start=request.start,
            end=request.end,
            is_adjusted=request.is_adjusted,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not prices:
        raise HTTPException(status_code=404, detail="KIS 일봉 데이터가 없습니다.")

    try:
        with SessionLocal() as session:
            response = _save_kis_daily_prices(session=session, request=request, prices=prices)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"KIS 일봉 DB 저장 실패: {exc.__class__.__name__}",
        ) from exc

    return response


@app.post("/api/data/kis/daily-prices/import/strategy", status_code=201)
async def import_kis_daily_prices_for_strategy(
    request: KisDailyPriceBatchImportRequest,
) -> KisDailyPriceBatchImportResponse:
    strategy = _find_system_strategy(request.strategy_code)
    user_strategy = None

    if strategy is None and request.strategy_code.startswith("user-"):
        user_strategy = _load_active_user_strategy(request.strategy_code)

    if strategy is None and user_strategy is None:
        raise HTTPException(status_code=404, detail="전략을 찾지 못했습니다.")

    return _import_kis_daily_prices_for_strategy_candidates(request)


def _import_kis_daily_prices_for_strategy_candidates(
    request: KisDailyPriceBatchImportRequest,
) -> KisDailyPriceBatchImportResponse:
    candidates = _seed_candidates_for_strategy(request.strategy_code, limit=request.max_symbols)
    items: list[KisDailyPriceBatchImportItem] = []

    for candidate in candidates:
        import_request = KisDailyPriceImportRequest(
            symbol=str(candidate["symbol"]),
            name=str(candidate["name"]),
            exchange=str(candidate["exchange"]),
            start=request.start,
            end=request.end,
            is_adjusted=request.is_adjusted,
        )

        try:
            prices = fetch_kis_daily_prices(
                symbol=import_request.symbol,
                start=import_request.start,
                end=import_request.end,
                is_adjusted=import_request.is_adjusted,
            )

            if not prices:
                items.append(
                    KisDailyPriceBatchImportItem(
                        symbol=import_request.symbol,
                        name=import_request.name or import_request.symbol,
                        exchange=import_request.exchange,
                        status="failed",
                        saved_count=0,
                        message="KIS 일봉 데이터 없음",
                    )
                )
                continue

            with SessionLocal() as session:
                saved = _save_kis_daily_prices(
                    session=session,
                    request=import_request,
                    prices=prices,
                )

            items.append(
                KisDailyPriceBatchImportItem(
                    symbol=saved.symbol,
                    name=import_request.name or saved.symbol,
                    exchange=saved.exchange,
                    status="completed",
                    saved_count=saved.saved_count,
                    message=saved.message,
                )
            )
        except (MarketDataProviderUnavailable, SQLAlchemyError, ValueError) as exc:
            items.append(
                KisDailyPriceBatchImportItem(
                    symbol=import_request.symbol,
                    name=import_request.name or import_request.symbol,
                    exchange=import_request.exchange,
                    status="failed",
                    saved_count=0,
                    message=str(exc),
                )
            )

    success_count = sum(1 for item in items if item.status == "completed")
    saved_count = sum(item.saved_count for item in items)

    return KisDailyPriceBatchImportResponse(
        provider="KIS Open API",
        strategy_code=request.strategy_code,
        requested_symbols=len(candidates),
        success_count=success_count,
        failed_count=len(items) - success_count,
        saved_count=saved_count,
        items=items,
    )


@app.get("/api/data/yahoo/daily-prices")
async def yahoo_daily_prices(
    symbol: str,
    exchange: str = "KOSPI",
    start: date | None = None,
    end: date | None = None,
    limit: int = 120,
) -> YahooDailyPricePreviewResponse:
    safe_limit = max(1, min(limit, 500))

    try:
        prices = fetch_yahoo_daily_prices(symbol=symbol, exchange=exchange, start=start, end=end)
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    limited_prices = prices[-safe_limit:]

    return YahooDailyPricePreviewResponse(
        provider="Yahoo Finance",
        symbol=symbol.strip().upper(),
        yahoo_symbol=normalize_yahoo_symbol(symbol, exchange),
        exchange=exchange.strip().upper(),
        count=len(limited_prices),
        prices=[YahooDailyPrice(**item) for item in limited_prices],
    )


@app.post("/api/data/yahoo/daily-prices/import", status_code=201)
async def import_yahoo_daily_prices(
    request: YahooDailyPriceImportRequest,
) -> YahooDailyPriceImportResponse:
    try:
        prices = fetch_yahoo_daily_prices(
            symbol=request.symbol,
            exchange=request.exchange,
            start=request.start,
            end=request.end,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not prices:
        raise HTTPException(status_code=404, detail="Yahoo 일봉 데이터가 없습니다.")

    try:
        with SessionLocal() as session:
            response = _save_yahoo_daily_prices(session=session, request=request, prices=prices)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Yahoo 일봉 DB 저장 실패: {exc.__class__.__name__}",
        ) from exc

    return response


@app.post("/api/data/yahoo/daily-prices/import/strategy", status_code=201)
async def import_yahoo_daily_prices_for_strategy(
    request: YahooDailyPriceBatchImportRequest,
) -> YahooDailyPriceBatchImportResponse:
    strategy = _find_system_strategy(request.strategy_code)
    user_strategy = None

    if strategy is None and request.strategy_code.startswith("user-"):
        user_strategy = _load_active_user_strategy(request.strategy_code)

    if strategy is None and user_strategy is None:
        raise HTTPException(status_code=404, detail="전략을 찾지 못했습니다.")

    return _import_yahoo_daily_prices_for_strategy_candidates(request)


def _import_yahoo_daily_prices_for_strategy_candidates(
    request: YahooDailyPriceBatchImportRequest,
) -> YahooDailyPriceBatchImportResponse:
    candidates = _seed_candidates_for_strategy(request.strategy_code, limit=request.max_symbols)
    items: list[YahooDailyPriceBatchImportItem] = []

    for candidate in candidates:
        import_request = YahooDailyPriceImportRequest(
            symbol=str(candidate["symbol"]),
            name=str(candidate["name"]),
            exchange=str(candidate["exchange"]),
            start=request.start,
            end=request.end,
            is_adjusted=request.is_adjusted,
        )

        try:
            prices = fetch_yahoo_daily_prices(
                symbol=import_request.symbol,
                exchange=import_request.exchange,
                start=import_request.start,
                end=import_request.end,
            )

            if not prices:
                items.append(
                    YahooDailyPriceBatchImportItem(
                        symbol=import_request.symbol,
                        name=import_request.name or import_request.symbol,
                        exchange=import_request.exchange,
                        status="failed",
                        saved_count=0,
                        message="Yahoo 일봉 데이터 없음",
                    )
                )
                continue

            with SessionLocal() as session:
                saved = _save_yahoo_daily_prices(
                    session=session,
                    request=import_request,
                    prices=prices,
                )

            items.append(
                YahooDailyPriceBatchImportItem(
                    symbol=saved.symbol,
                    name=import_request.name or saved.symbol,
                    exchange=saved.exchange,
                    status="completed",
                    saved_count=saved.saved_count,
                    message=saved.message,
                )
            )
        except (MarketDataProviderUnavailable, SQLAlchemyError, ValueError) as exc:
            items.append(
                YahooDailyPriceBatchImportItem(
                    symbol=import_request.symbol,
                    name=import_request.name or import_request.symbol,
                    exchange=import_request.exchange,
                    status="failed",
                    saved_count=0,
                    message=str(exc),
                )
            )

    success_count = sum(1 for item in items if item.status == "completed")
    saved_count = sum(item.saved_count for item in items)

    return YahooDailyPriceBatchImportResponse(
        provider="Yahoo Finance",
        strategy_code=request.strategy_code,
        requested_symbols=len(candidates),
        success_count=success_count,
        failed_count=len(items) - success_count,
        saved_count=saved_count,
        items=items,
    )


def _save_yahoo_daily_prices(
    *,
    session,
    request: YahooDailyPriceImportRequest,
    prices: list[dict[str, object]],
) -> YahooDailyPriceImportResponse:
    yahoo_symbol = normalize_yahoo_symbol(request.symbol, request.exchange)
    market = _get_or_create_market(session, normalize_market_code(request.exchange))
    instrument = _get_or_create_instrument(
        session=session,
        market=market,
        symbol=request.symbol.strip().upper(),
        name=request.name or request.symbol.strip().upper(),
        exchange=request.exchange.strip().upper(),
    )
    job = DataImportJob(
        provider="Yahoo Finance",
        job_type="daily_prices",
        status="running",
        message=f"{yahoo_symbol} 일봉 수집 중",
    )
    session.add(job)
    session.flush()

    saved_count = 0
    for row in prices:
        trade_date = _row_trade_date(row)
        close_price = _decimal_or_none(row.get("adjusted_close") if request.is_adjusted else row.get("close"))
        raw_close_price = _decimal_or_none(row.get("close"))

        if close_price is None or raw_close_price is None:
            continue

        open_price = _decimal_or_none(row.get("open")) or raw_close_price
        high_price = _decimal_or_none(row.get("high")) or raw_close_price
        low_price = _decimal_or_none(row.get("low")) or raw_close_price
        open_price, high_price, low_price, close_price = _normalize_ohlcv_prices(
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )
        volume = int(row.get("volume") or 0)

        existing = session.scalar(
            select(DailyPrice).where(
                DailyPrice.instrument_id == instrument.id,
                DailyPrice.trade_date == trade_date,
                DailyPrice.provider == "Yahoo Finance",
                DailyPrice.is_adjusted == request.is_adjusted,
            )
        )

        if existing is None:
            session.add(
                DailyPrice(
                    instrument_id=instrument.id,
                    trade_date=trade_date,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    volume=volume,
                    trading_value=None,
                    provider="Yahoo Finance",
                    is_adjusted=request.is_adjusted,
                )
            )
        else:
            existing.open_price = open_price
            existing.high_price = high_price
            existing.low_price = low_price
            existing.close_price = close_price
            existing.volume = volume
            existing.trading_value = None

        saved_count += 1

    job.status = "completed"
    job.finished_at = now_kst_naive()
    job.message = f"{yahoo_symbol} 일봉 {saved_count}건 저장"
    session.commit()

    return YahooDailyPriceImportResponse(
        provider="Yahoo Finance",
        job_id=job.id,
        symbol=request.symbol.strip().upper(),
        yahoo_symbol=yahoo_symbol,
        exchange=request.exchange.strip().upper(),
        fetched_count=len(prices),
        saved_count=saved_count,
        message=job.message,
    )


def _save_krx_instruments(
    *,
    market: str,
    base_date: str,
    rows: list[dict[str, object]],
) -> KrxInstrumentImportResponse:
    normalized_market = market.strip().upper() or "ALL"

    with SessionLocal() as session:
        kr_market = _get_or_create_kr_market(session)
        job = DataImportJob(
            provider="KRX Open API",
            job_type="instruments",
            status="running",
            message=f"KRX {normalized_market} 종목 목록 저장 중",
        )
        session.add(job)
        session.flush()

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for row in rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            name = str(row.get("name") or "").strip()
            exchange = str(row.get("exchange") or "").strip().upper()
            asset_type = str(row.get("asset_type") or "stock").strip().lower() or "stock"

            if not symbol or not name:
                skipped_count += 1
                continue

            if not exchange:
                exchange = normalized_market if normalized_market != "ALL" else "KRX"

            existing = session.scalar(
                select(Instrument).where(
                    Instrument.market_id == kr_market.id,
                    Instrument.symbol == symbol,
                )
            )

            if existing is None:
                instrument = _get_or_create_instrument(
                    session=session,
                    market=kr_market,
                    symbol=symbol,
                    name=name,
                    exchange=exchange,
                )
                instrument.asset_type = asset_type
                created_count += 1
                continue

            changed = (
                existing.name != name
                or existing.exchange != exchange
                or existing.asset_type != asset_type
                or not existing.is_active
            )
            existing.name = name
            existing.exchange = exchange
            existing.asset_type = asset_type
            existing.is_active = True
            if changed:
                updated_count += 1

        instrument_count = session.scalar(
            select(func.count()).select_from(Instrument).where(Instrument.market_id == kr_market.id)
        ) or 0

        job.status = "completed"
        job.finished_at = now_kst_naive()
        job.message = (
            f"KRX {base_date} 기준 {len(rows)}건 확인, 신규 {created_count}건, "
            f"갱신 {updated_count}건, 스킵 {skipped_count}건"
        )
        session.commit()

        return KrxInstrumentImportResponse(
            provider="KRX Open API",
            job_id=job.id,
            market=normalized_market,
            base_date=base_date,
            fetched_count=len(rows),
            created_count=created_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            instrument_count=instrument_count,
            message=job.message,
        )


def _save_kis_instruments_from_market_cap_ranking(
    *,
    market: str,
    rows: list[dict[str, object]],
) -> KisInstrumentImportResponse:
    normalized_market = market.strip().upper() or "ALL"

    with SessionLocal() as session:
        kr_market = _get_or_create_kr_market(session)
        job = DataImportJob(
            provider="KIS Open API",
            job_type="instruments",
            status="running",
            message=f"KIS 시가총액 랭킹 기반 {normalized_market} 종목 목록 저장 중",
        )
        session.add(job)
        session.flush()

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for row in rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            name = str(row.get("name") or "").strip()
            exchange = str(row.get("exchange") or "").strip().upper()

            if not symbol or not name:
                skipped_count += 1
                continue

            if not exchange:
                exchange = normalized_market if normalized_market != "ALL" else "KRX"

            existing = session.scalar(
                select(Instrument).where(
                    Instrument.market_id == kr_market.id,
                    Instrument.symbol == symbol,
                )
            )

            if existing is None:
                _get_or_create_instrument(
                    session=session,
                    market=kr_market,
                    symbol=symbol,
                    name=name,
                    exchange=exchange,
                )
                created_count += 1
                continue

            changed = existing.name != name or existing.exchange != exchange or not existing.is_active
            existing.name = name
            existing.exchange = exchange
            existing.is_active = True
            if changed:
                updated_count += 1

        instrument_count = session.scalar(
            select(func.count()).select_from(Instrument).where(Instrument.market_id == kr_market.id)
        ) or 0

        job.status = "completed"
        job.finished_at = now_kst_naive()
        job.message = (
            f"KIS 랭킹 {len(rows)}건 확인, 신규 {created_count}건, 갱신 {updated_count}건, "
            f"스킵 {skipped_count}건"
        )
        session.commit()

        return KisInstrumentImportResponse(
            provider="KIS Open API",
            job_id=job.id,
            market=normalized_market,
            fetched_count=len(rows),
            created_count=created_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            instrument_count=instrument_count,
            message=job.message,
        )


def _save_krx_daily_prices(
    *,
    session,
    request: KrxDailyPriceImportRequest,
    prices: list[dict[str, object]],
) -> KrxDailyPriceImportResponse:
    symbol = request.symbol.strip().upper()
    market = _get_or_create_kr_market(session)
    instrument = _get_or_create_instrument(
        session=session,
        market=market,
        symbol=symbol,
        name=request.name or symbol,
        exchange=request.exchange.strip().upper(),
    )
    job = DataImportJob(
        provider="KRX Open API",
        job_type="daily_prices",
        status="running",
        message=f"{symbol} KRX 일봉 수집 중",
    )
    session.add(job)
    session.flush()

    saved_count = 0
    for row in prices:
        trade_date = _row_trade_date(row)
        close_price = _decimal_or_none(row.get("close"))

        if close_price is None:
            continue

        open_price = _decimal_or_none(row.get("open")) or close_price
        high_price = _decimal_or_none(row.get("high")) or close_price
        low_price = _decimal_or_none(row.get("low")) or close_price
        open_price, high_price, low_price, close_price = _normalize_ohlcv_prices(
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )
        volume = int(row.get("volume") or 0)
        trading_value = _decimal_or_none(row.get("trading_value"))

        existing = session.scalar(
            select(DailyPrice).where(
                DailyPrice.instrument_id == instrument.id,
                DailyPrice.trade_date == trade_date,
                DailyPrice.provider == "KRX Open API",
                DailyPrice.is_adjusted.is_(False),
            )
        )

        if existing is None:
            session.add(
                DailyPrice(
                    instrument_id=instrument.id,
                    trade_date=trade_date,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    volume=volume,
                    trading_value=trading_value,
                    provider="KRX Open API",
                    is_adjusted=False,
                )
            )
        else:
            existing.open_price = open_price
            existing.high_price = high_price
            existing.low_price = low_price
            existing.close_price = close_price
            existing.volume = volume
            existing.trading_value = trading_value

        saved_count += 1

    job.status = "completed"
    job.finished_at = now_kst_naive()
    job.message = f"{symbol} KRX 일봉 {saved_count}건 저장"
    session.commit()

    return KrxDailyPriceImportResponse(
        provider="KRX Open API",
        job_id=job.id,
        symbol=symbol,
        exchange=request.exchange.strip().upper(),
        fetched_count=len(prices),
        saved_count=saved_count,
        message=job.message,
    )


def _save_krx_market_daily_prices(
    *,
    session,
    request: KrxMarketDailyPriceImportRequest,
    prices: list[dict[str, object]],
) -> KrxMarketDailyPriceImportResponse:
    normalized_market = request.market.strip().upper() or "KOSPI"
    market = _get_or_create_kr_market(session)
    job = DataImportJob(
        provider="KRX Open API",
        job_type="market_daily_prices",
        status="running",
        message=f"{normalized_market} KRX 시장 일봉 수집 중",
    )
    session.add(job)
    session.flush()

    symbols = sorted({str(row.get("symbol") or "").strip().upper() for row in prices if row.get("symbol")})
    existing_instruments = {
        instrument.symbol: instrument
        for instrument in session.scalars(select(Instrument).where(Instrument.symbol.in_(symbols))).all()
    }
    for symbol in symbols:
        if symbol in existing_instruments:
            continue
        source_row = next(row for row in prices if str(row.get("symbol") or "").strip().upper() == symbol)
        instrument = _get_or_create_instrument(
            session=session,
            market=market,
            symbol=symbol,
            name=str(source_row.get("name") or symbol),
            exchange=_normalize_exchange(str(source_row.get("exchange") or normalized_market)),
        )
        existing_instruments[symbol] = instrument
    session.flush()

    instrument_ids = [instrument.id for instrument in existing_instruments.values()]
    existing_prices = {
        (row.instrument_id, row.trade_date): row
        for row in session.scalars(
            select(DailyPrice).where(
                DailyPrice.instrument_id.in_(instrument_ids),
                DailyPrice.trade_date >= request.start,
                DailyPrice.trade_date <= request.end,
                DailyPrice.provider == "KRX Open API",
                DailyPrice.is_adjusted.is_(False),
            )
        ).all()
    }

    saved_count = 0
    for row in prices:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue

        instrument = existing_instruments.get(symbol)
        if instrument is None:
            continue

        trade_date = _row_trade_date(row)
        close_price = _decimal_or_none(row.get("close"))
        if close_price is None:
            continue

        open_price = _decimal_or_none(row.get("open")) or close_price
        high_price = _decimal_or_none(row.get("high")) or close_price
        low_price = _decimal_or_none(row.get("low")) or close_price
        open_price, high_price, low_price, close_price = _normalize_ohlcv_prices(
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )
        volume = int(row.get("volume") or 0)
        trading_value = _decimal_or_none(row.get("trading_value"))

        existing = existing_prices.get((instrument.id, trade_date))

        if existing is None:
            existing = DailyPrice(
                instrument_id=instrument.id,
                trade_date=trade_date,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
                trading_value=trading_value,
                provider="KRX Open API",
                is_adjusted=False,
            )
            session.add(existing)
            existing_prices[(instrument.id, trade_date)] = existing
        existing.open_price = open_price
        existing.high_price = high_price
        existing.low_price = low_price
        existing.close_price = close_price
        existing.volume = volume
        existing.trading_value = trading_value

        saved_count += 1

    job.status = "completed"
    job.finished_at = now_kst_naive()
    job.message = (
        f"{normalized_market} KRX 시장 일봉 {saved_count}건 저장 "
        f"({request.start.isoformat()} ~ {request.end.isoformat()})"
    )
    session.commit()

    return KrxMarketDailyPriceImportResponse(
        provider="KRX Open API",
        job_id=job.id,
        market=normalized_market,
        start=request.start,
        end=request.end,
        fetched_count=len(prices),
        saved_count=saved_count,
        message=job.message,
    )


def _save_kis_daily_prices(
    *,
    session,
    request: KisDailyPriceImportRequest,
    prices: list[dict[str, object]],
) -> KisDailyPriceImportResponse:
    symbol = request.symbol.strip().upper()
    market = _get_or_create_kr_market(session)
    instrument = _get_or_create_instrument(
        session=session,
        market=market,
        symbol=symbol,
        name=request.name or symbol,
        exchange=request.exchange.strip().upper(),
    )
    job = DataImportJob(
        provider="KIS Open API",
        job_type="daily_prices",
        status="running",
        message=f"{symbol} KIS 일봉 수집 중",
    )
    session.add(job)
    session.flush()

    saved_count = 0
    for row in prices:
        trade_date = _row_trade_date(row)
        close_price = _decimal_or_none(row.get("adjusted_close") if request.is_adjusted else row.get("close"))
        raw_close_price = _decimal_or_none(row.get("close"))

        if close_price is None or raw_close_price is None:
            continue

        open_price = _decimal_or_none(row.get("open")) or raw_close_price
        high_price = _decimal_or_none(row.get("high")) or raw_close_price
        low_price = _decimal_or_none(row.get("low")) or raw_close_price
        open_price, high_price, low_price, close_price = _normalize_ohlcv_prices(
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
        )
        volume = int(row.get("volume") or 0)
        trading_value = _decimal_or_none(row.get("trading_value"))

        existing = session.scalar(
            select(DailyPrice).where(
                DailyPrice.instrument_id == instrument.id,
                DailyPrice.trade_date == trade_date,
                DailyPrice.provider == "KIS Open API",
                DailyPrice.is_adjusted == request.is_adjusted,
            )
        )

        if existing is None:
            session.add(
                DailyPrice(
                    instrument_id=instrument.id,
                    trade_date=trade_date,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    volume=volume,
                    trading_value=trading_value,
                    provider="KIS Open API",
                    is_adjusted=request.is_adjusted,
                )
            )
        else:
            existing.open_price = open_price
            existing.high_price = high_price
            existing.low_price = low_price
            existing.close_price = close_price
            existing.volume = volume
            existing.trading_value = trading_value

        saved_count += 1

    job.status = "completed"
    job.finished_at = now_kst_naive()
    job.message = f"{symbol} KIS 일봉 {saved_count}건 저장"
    session.commit()

    return KisDailyPriceImportResponse(
        provider="KIS Open API",
        job_id=job.id,
        symbol=symbol,
        exchange=request.exchange.strip().upper(),
        fetched_count=len(prices),
        saved_count=saved_count,
        message=job.message,
    )


def _save_kis_quote_snapshot(
    *,
    session,
    quote: dict[str, object],
    fallback_name: str,
    fallback_exchange: str,
) -> None:
    symbol = str(quote.get("symbol") or "").strip().upper()
    if not symbol:
        raise ValueError("KIS 현재가 응답에 종목코드가 없습니다.")

    market = _get_or_create_kr_market(session)
    instrument = _get_or_create_instrument(
        session=session,
        market=market,
        symbol=symbol,
        name=str(quote.get("name") or fallback_name or symbol),
        exchange=fallback_exchange.strip().upper() or "KOSPI",
    )
    snapshot_date = today_kst()
    existing = session.scalar(
        select(QuoteSnapshot).where(
            QuoteSnapshot.instrument_id == instrument.id,
            QuoteSnapshot.snapshot_date == snapshot_date,
            QuoteSnapshot.provider == KIS_QUOTE_SNAPSHOT_PROVIDER,
        )
    )
    values = {
        "price": _decimal_or_none(quote.get("price")),
        "change_pct": _decimal_or_none(quote.get("change_rate")),
        "volume": int(quote["volume"]) if quote.get("volume") is not None else None,
        "trading_value": _decimal_or_none(quote.get("trading_value")),
        "market_cap": _decimal_or_none(quote.get("market_cap")),
        "per": _decimal_or_none(quote.get("per")),
        "pbr": _decimal_or_none(quote.get("pbr")),
        "eps": _decimal_or_none(quote.get("eps")),
        "bps": _decimal_or_none(quote.get("bps")),
        "turnover_pct": _decimal_or_none(quote.get("turnover_pct")),
        "foreign_holding_rate": _decimal_or_none(quote.get("foreign_holding_rate")),
        "foreign_net_buy_qty": int(quote["foreign_net_buy_qty"])
        if quote.get("foreign_net_buy_qty") is not None
        else None,
        "program_net_buy_qty": int(quote["program_net_buy_qty"])
        if quote.get("program_net_buy_qty") is not None
        else None,
        "high_52w": _decimal_or_none(quote.get("high_52w")),
        "low_52w": _decimal_or_none(quote.get("low_52w")),
    }

    if existing is None:
        session.add(
            QuoteSnapshot(
                instrument_id=instrument.id,
                snapshot_date=snapshot_date,
                provider=KIS_QUOTE_SNAPSHOT_PROVIDER,
                **values,
            )
        )
    else:
        for key, value in values.items():
            setattr(existing, key, value)
        existing.created_at = now_kst_naive()

    session.commit()


def _save_kis_supply_flows(
    *,
    session,
    symbol: str,
    name: str,
    exchange: str,
    flows: list[dict[str, object]],
) -> int:
    normalized_symbol = symbol.strip().upper()
    market = _get_or_create_kr_market(session)
    instrument = _get_or_create_instrument(
        session=session,
        market=market,
        symbol=normalized_symbol,
        name=name or normalized_symbol,
        exchange=exchange.strip().upper() or "KOSPI",
    )
    saved_count = 0

    for flow in flows:
        trade_date = _row_trade_date(flow)
        values = {
            "foreign_net_buy_qty": int(flow["foreign_net_buy_qty"])
            if flow.get("foreign_net_buy_qty") is not None
            else None,
            "institution_net_buy_qty": int(flow["institution_net_buy_qty"])
            if flow.get("institution_net_buy_qty") is not None
            else None,
            "pension_net_buy_qty": int(flow["pension_net_buy_qty"])
            if flow.get("pension_net_buy_qty") is not None
            else None,
            "foreign_net_buy_value": _decimal_or_none(flow.get("foreign_net_buy_value")),
            "institution_net_buy_value": _decimal_or_none(flow.get("institution_net_buy_value")),
            "pension_net_buy_value": _decimal_or_none(flow.get("pension_net_buy_value")),
            "individual_net_buy_value": _decimal_or_none(flow.get("individual_net_buy_value")),
        }
        existing = session.scalar(
            select(SupplyFlowDaily).where(
                SupplyFlowDaily.instrument_id == instrument.id,
                SupplyFlowDaily.trade_date == trade_date,
                SupplyFlowDaily.provider == KIS_SUPPLY_FLOW_PROVIDER,
            )
        )

        if existing is None:
            session.add(
                SupplyFlowDaily(
                    instrument_id=instrument.id,
                    trade_date=trade_date,
                    provider=KIS_SUPPLY_FLOW_PROVIDER,
                    **values,
                )
            )
        else:
            for key, value in values.items():
                setattr(existing, key, value)

        saved_count += 1

    session.commit()
    return saved_count


def _save_kis_risk_indicators(
    *,
    session,
    symbol: str,
    name: str,
    exchange: str,
    short_sale_rows: list[dict[str, object]],
    credit_balance_rows: list[dict[str, object]],
) -> int:
    normalized_symbol = symbol.strip().upper()
    market = _get_or_create_kr_market(session)
    instrument = _get_or_create_instrument(
        session=session,
        market=market,
        symbol=normalized_symbol,
        name=name or normalized_symbol,
        exchange=exchange.strip().upper() or "KOSPI",
    )

    rows_by_date: dict[date, dict[str, object]] = {}
    for row in short_sale_rows:
        trade_date = _row_trade_date(row)
        rows_by_date.setdefault(trade_date, {}).update(
            {
                "short_sale_volume": row.get("short_sale_volume"),
                "short_sale_volume_ratio": row.get("short_sale_volume_ratio"),
                "short_sale_value": row.get("short_sale_value"),
                "short_sale_value_ratio": row.get("short_sale_value_ratio"),
            }
        )

    for row in credit_balance_rows:
        trade_date = _row_trade_date(row)
        rows_by_date.setdefault(trade_date, {}).update(
            {
                "margin_loan_balance": row.get("margin_loan_balance"),
                "margin_loan_balance_rate": row.get("margin_loan_balance_rate"),
                "margin_loan_new_amount": row.get("margin_loan_new_amount"),
                "margin_loan_redeem_amount": row.get("margin_loan_redeem_amount"),
                "stock_loan_balance": row.get("stock_loan_balance"),
                "stock_loan_balance_rate": row.get("stock_loan_balance_rate"),
            }
        )

    saved_count = 0
    for trade_date, row in rows_by_date.items():
        values = {
            "short_sale_volume": int(row["short_sale_volume"])
            if row.get("short_sale_volume") is not None
            else None,
            "short_sale_volume_ratio": _decimal_or_none(row.get("short_sale_volume_ratio")),
            "short_sale_value": _decimal_or_none(row.get("short_sale_value")),
            "short_sale_value_ratio": _decimal_or_none(row.get("short_sale_value_ratio")),
            "margin_loan_balance": _decimal_or_none(row.get("margin_loan_balance")),
            "margin_loan_balance_rate": _decimal_or_none(row.get("margin_loan_balance_rate")),
            "margin_loan_new_amount": _decimal_or_none(row.get("margin_loan_new_amount")),
            "margin_loan_redeem_amount": _decimal_or_none(row.get("margin_loan_redeem_amount")),
            "stock_loan_balance": _decimal_or_none(row.get("stock_loan_balance")),
            "stock_loan_balance_rate": _decimal_or_none(row.get("stock_loan_balance_rate")),
        }
        existing = session.scalar(
            select(RiskIndicatorDaily).where(
                RiskIndicatorDaily.instrument_id == instrument.id,
                RiskIndicatorDaily.trade_date == trade_date,
                RiskIndicatorDaily.provider == KIS_RISK_INDICATOR_PROVIDER,
            )
        )

        if existing is None:
            session.add(
                RiskIndicatorDaily(
                    instrument_id=instrument.id,
                    trade_date=trade_date,
                    provider=KIS_RISK_INDICATOR_PROVIDER,
                    **values,
                )
            )
        else:
            for key, value in values.items():
                if value is not None:
                    setattr(existing, key, value)

        saved_count += 1

    session.commit()
    return saved_count


def _save_kis_fundamental_ratios(
    *,
    session,
    symbol: str,
    name: str,
    exchange: str,
    ratios: list[dict[str, object]],
) -> int:
    normalized_symbol = symbol.strip().upper()
    market = _get_or_create_kr_market(session)
    instrument = _get_or_create_instrument(
        session=session,
        market=market,
        symbol=normalized_symbol,
        name=name or normalized_symbol,
        exchange=exchange.strip().upper() or "KOSPI",
    )

    saved_count = 0
    for row in ratios:
        fiscal_period = str(row.get("fiscal_period") or "").strip()
        period_type = str(row.get("period_type") or "annual").strip().lower()
        if not fiscal_period:
            continue

        values = {
            "revenue_growth": _decimal_or_none(row.get("revenue_growth")),
            "operating_income_growth": _decimal_or_none(row.get("operating_income_growth")),
            "net_income_growth": _decimal_or_none(row.get("net_income_growth")),
            "roe": _decimal_or_none(row.get("roe")),
            "roa": _decimal_or_none(row.get("roa")),
            "operating_margin": _decimal_or_none(row.get("operating_margin")),
            "net_margin": _decimal_or_none(row.get("net_margin")),
            "free_cash_flow": _decimal_or_none(row.get("free_cash_flow")),
            "dividends_paid": _decimal_or_none(row.get("dividends_paid")),
            "current_assets": _decimal_or_none(row.get("current_assets")),
            "current_liabilities": _decimal_or_none(row.get("current_liabilities")),
            "cash_and_cash_equivalents": _decimal_or_none(row.get("cash_and_cash_equivalents")),
            "ebitda": _decimal_or_none(row.get("ebitda")),
            "fcf_yield": _decimal_or_none(row.get("fcf_yield")),
            "ev_ebitda": _decimal_or_none(row.get("ev_ebitda")),
            "dividend_yield": _decimal_or_none(row.get("dividend_yield")),
            "payout_ratio": _decimal_or_none(row.get("payout_ratio")),
            "current_ratio": _decimal_or_none(row.get("current_ratio")),
            "dividend_growth": _decimal_or_none(row.get("dividend_growth")),
            "dividend_streak_years": _int_or_none(row.get("dividend_streak_years")),
            "dividend_stability_score": _int_or_none(row.get("dividend_stability_score")),
            "eps": _decimal_or_none(row.get("eps")),
            "sps": _decimal_or_none(row.get("sps")),
            "bps": _decimal_or_none(row.get("bps")),
            "reserve_ratio": _decimal_or_none(row.get("reserve_ratio")),
            "debt_ratio": _decimal_or_none(row.get("debt_ratio")),
        }
        existing = session.scalar(
            select(FundamentalRatio).where(
                FundamentalRatio.instrument_id == instrument.id,
                FundamentalRatio.fiscal_period == fiscal_period,
                FundamentalRatio.period_type == period_type,
                FundamentalRatio.provider == KIS_FUNDAMENTAL_PROVIDER,
            )
        )

        if existing is None:
            session.add(
                FundamentalRatio(
                    instrument_id=instrument.id,
                    fiscal_period=fiscal_period,
                    period_type=period_type,
                    provider=KIS_FUNDAMENTAL_PROVIDER,
                    **values,
                )
            )
        else:
            for key, value in values.items():
                if value is not None:
                    setattr(existing, key, value)

        saved_count += 1

    session.commit()
    return saved_count


def _save_open_dart_fundamental_summary(
    *,
    session,
    symbol: str,
    name: str,
    exchange: str,
    business_year: int,
    summary: dict[str, object],
) -> int:
    normalized_symbol = symbol.strip().upper()
    market = _get_or_create_kr_market(session)
    instrument = _get_or_create_instrument(
        session=session,
        market=market,
        symbol=normalized_symbol,
        name=name or normalized_symbol,
        exchange=exchange.strip().upper() or "KOSPI",
    )
    fiscal_period = f"{business_year}12"
    market_cap = _latest_market_cap_for_instrument(session=session, instrument_id=instrument.id)
    free_cash_flow = _decimal_or_none(summary.get("free_cash_flow"))
    dividends_paid = _decimal_or_none(summary.get("dividends_paid"))
    net_income = _decimal_or_none(summary.get("net_income"))
    liabilities = _decimal_or_none(summary.get("liabilities"))
    current_assets = _decimal_or_none(summary.get("current_assets"))
    current_liabilities = _decimal_or_none(summary.get("current_liabilities"))
    cash_and_cash_equivalents = _decimal_or_none(summary.get("cash_and_cash_equivalents"))
    ebitda = _decimal_or_none(summary.get("ebitda"))
    fcf_yield = _percent_from_amount(free_cash_flow, market_cap)
    dividend_yield = _percent_from_amount(dividends_paid, market_cap)
    payout_ratio = _percent_from_amount(dividends_paid, net_income)
    ev_ebitda = _ev_ebitda_ratio(
        market_cap=market_cap,
        liabilities=liabilities,
        cash_and_cash_equivalents=cash_and_cash_equivalents,
        ebitda=ebitda,
    )
    dividend_growth = _decimal_or_none(summary.get("dividend_growth"))
    dividend_stability_score = _dividend_stability_score_from_values(
        dividend_yield=dividend_yield,
        payout_ratio=payout_ratio,
        fcf_yield=fcf_yield,
        dividend_growth=dividend_growth,
        debt_ratio=_decimal_or_none(summary.get("debt_ratio")),
    )
    values = {
        "revenue_growth": _decimal_or_none(summary.get("revenue_growth")),
        "operating_income_growth": _decimal_or_none(summary.get("operating_income_growth")),
        "net_income_growth": _decimal_or_none(summary.get("net_income_growth")),
        "roe": _decimal_or_none(summary.get("roe")),
        "roa": _decimal_or_none(summary.get("roa")),
        "operating_margin": _decimal_or_none(summary.get("operating_margin")),
        "net_margin": _decimal_or_none(summary.get("net_margin")),
        "free_cash_flow": free_cash_flow,
        "dividends_paid": dividends_paid,
        "current_assets": current_assets,
        "current_liabilities": current_liabilities,
        "cash_and_cash_equivalents": cash_and_cash_equivalents,
        "ebitda": ebitda,
        "fcf_yield": fcf_yield,
        "ev_ebitda": ev_ebitda,
        "dividend_yield": dividend_yield,
        "payout_ratio": payout_ratio,
        "current_ratio": _decimal_or_none(summary.get("current_ratio")),
        "dividend_growth": dividend_growth,
        "dividend_streak_years": 1 if dividends_paid is not None and dividends_paid > 0 else None,
        "dividend_stability_score": dividend_stability_score,
        "eps": None,
        "sps": None,
        "bps": None,
        "reserve_ratio": None,
        "debt_ratio": _decimal_or_none(summary.get("debt_ratio")),
    }
    if not any(value is not None for value in values.values()):
        return 0

    existing = session.scalar(
        select(FundamentalRatio).where(
            FundamentalRatio.instrument_id == instrument.id,
            FundamentalRatio.fiscal_period == fiscal_period,
            FundamentalRatio.period_type == "annual",
            FundamentalRatio.provider == OPEN_DART_FUNDAMENTAL_PROVIDER,
        )
    )

    if existing is None:
        session.add(
            FundamentalRatio(
                instrument_id=instrument.id,
                fiscal_period=fiscal_period,
                period_type="annual",
                provider=OPEN_DART_FUNDAMENTAL_PROVIDER,
                **values,
            )
        )
    else:
        for key, value in values.items():
            if value is not None:
                setattr(existing, key, value)

    session.commit()
    return 1


def _latest_market_cap_for_instrument(*, session, instrument_id: int) -> Decimal | None:
    value = session.scalar(
        select(QuoteSnapshot.market_cap)
        .where(
            QuoteSnapshot.instrument_id == instrument_id,
            QuoteSnapshot.market_cap.is_not(None),
        )
        .order_by(QuoteSnapshot.snapshot_date.desc(), QuoteSnapshot.id.desc())
    )
    return _decimal_or_none(value)


def _percent_from_amount(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return (numerator / denominator * Decimal("100")).quantize(Decimal("0.0001"))


def _ev_ebitda_ratio(
    *,
    market_cap: Decimal | None,
    liabilities: Decimal | None,
    cash_and_cash_equivalents: Decimal | None,
    ebitda: Decimal | None,
) -> Decimal | None:
    if market_cap is None or ebitda is None or ebitda <= 0:
        return None

    enterprise_value = market_cap + max(liabilities or Decimal("0"), Decimal("0"))
    enterprise_value -= max(cash_and_cash_equivalents or Decimal("0"), Decimal("0"))
    if enterprise_value <= 0:
        return None

    return (enterprise_value / ebitda).quantize(Decimal("0.0001"))


def _dividend_stability_score_from_values(
    *,
    dividend_yield: Decimal | None,
    payout_ratio: Decimal | None,
    fcf_yield: Decimal | None,
    dividend_growth: Decimal | None,
    debt_ratio: Decimal | None,
) -> int | None:
    if dividend_yield is None or dividend_yield <= 0:
        return None

    payout = float(payout_ratio or Decimal("25"))
    growth = float(dividend_growth or Decimal("0"))
    fcf = float(fcf_yield or Decimal("0"))
    debt = float(debt_ratio or Decimal("85"))
    score = (
        50
        + min(float(dividend_yield), 6) * 4
        + max(min(growth, 12), 0) * 1.2
        + max(min(fcf, 8), -4) * 2
        - max(payout - 65, 0) * 0.7
        - max(debt - 150, 0) * 0.12
    )
    return max(0, min(100, round(score)))


def _get_or_create_kr_market(session) -> Market:
    return _get_or_create_market(session, "KR")


def _get_or_create_market(session, market_code: str) -> Market:
    normalized_code = normalize_market_code(market_code)
    metadata = get_market_metadata(normalized_code)

    market = session.scalar(select(Market).where(Market.code == normalized_code))
    if market is not None:
        market.name = str(metadata["name"])
        market.country = str(metadata["country"])
        market.currency = str(metadata["currency"])
        market.timezone = str(metadata["timezone"])
        return market

    market = session.scalar(select(Market).where(Market.code == "KR"))
    if normalized_code == "KR" and market is not None:
        market.name = str(metadata["name"])
        market.country = str(metadata["country"])
        market.currency = str(metadata["currency"])
        market.timezone = str(metadata["timezone"])
        return market

    market = Market(
        code=normalized_code,
        name=str(metadata["name"]),
        country=str(metadata["country"]),
        currency=str(metadata["currency"]),
        timezone=str(metadata["timezone"]),
    )
    session.add(market)
    session.flush()
    return market


def _get_or_create_instrument(
    *,
    session,
    market: Market,
    symbol: str,
    name: str,
    exchange: str,
) -> Instrument:
    instrument = session.scalar(
        select(Instrument).where(
            Instrument.market_id == market.id,
            Instrument.symbol == symbol,
        )
    )
    if instrument is not None:
        instrument.name = name
        instrument.exchange = exchange
        instrument.is_active = True
        return instrument

    instrument = Instrument(
        market_id=market.id,
        symbol=symbol,
        name=name,
        exchange=exchange,
        asset_type="stock",
        is_active=True,
    )
    session.add(instrument)
    session.flush()
    return instrument


def _row_trade_date(row: dict[str, object]) -> date:
    value = row["trade_date"]
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("거래일 형식이 올바르지 않습니다.")


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return Decimal(str(value))


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return int(float(str(value)))


def _normalize_ohlcv_prices(
    *,
    open_price: Decimal,
    high_price: Decimal,
    low_price: Decimal,
    close_price: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    high = max(open_price, high_price, low_price, close_price)
    low = min(open_price, high_price, low_price, close_price)
    return open_price, high, low, close_price


def _decimal_or_float(value: object) -> float | None:
    decimal_value = _decimal_or_none(value)
    return float(decimal_value) if decimal_value is not None else None
