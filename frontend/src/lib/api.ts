import { env } from '$env/dynamic/public';

const API_BASE_URL = env.PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
const DEFAULT_REQUEST_TIMEOUT_MS = 12000;

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS
) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal
    });
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('서버 응답 시간이 길어져 요청을 중단했습니다. 잠시 후 다시 시도해 주세요.');
    }
    throw err;
  } finally {
    window.clearTimeout(timer);
  }
}

export type Strategy = {
  code: string;
  name: string;
  source_type: 'system' | 'user';
  category: string;
  style: string;
  holding_period: string;
  summary: string;
  rebalance_rule: string;
  data_requirements: string[];
  universe_filter: string[];
  signal_rules: string[];
  ranking_rules: string[];
  risk_controls: string[];
  risk_notes: string[];
  backtest_assumptions: string[];
  references: string[];
  performance: StrategyPerformanceSnapshot | null;
  default_enabled: boolean;
};

export type StrategyPerformanceWindow = {
  label: string;
  years: number;
  start_year: number;
  end_year: number;
  cagr: number | null;
  total_return: number | null;
  mdd: number | null;
  final_amount: number | null;
  status: 'complete' | 'partial' | 'unavailable' | string;
  note: string;
};

export type StrategyPerformanceSnapshot = {
  as_of: string;
  data_as_of: string | null;
  source: string;
  initial_amount: number;
  windows: StrategyPerformanceWindow[];
  update_policy: string;
  note: string;
};

export type StrategyPerformanceResponse = {
  strategy_code: string;
  performance: StrategyPerformanceSnapshot;
};

export type StrategyExecutionModeContract = {
  code: string;
  label: string;
  enabled: boolean;
  endpoint: string;
  note: string;
};

export type BacktestPolicy = {
  rebalance_interval_months: number;
  rebalance_label: string;
  rebalance_timing: string;
  return_price_basis: string;
  holding_count: number;
  weighting_method: string;
  rebalance_amount_rule: string;
  initial_rebalance_amount: number | null;
  trading_cost_pct: number;
  slippage_pct: number;
};

export type StrategyExecutionContract = {
  strategy_code: string;
  strategy_name: string;
  source_type: string;
  summary: string;
  formula: string;
  provider_priority: string[];
  backtest_policy: BacktestPolicy;
  safety_controls: string[];
  modes: StrategyExecutionModeContract[];
};

export type Recommendation = {
  symbol: string;
  name: string;
  market: string;
  strategy_code: string;
  score: number;
  signal: string;
  rationale: string[];
  risk_flags: string[];
};

export type StrategyCandidateResult = {
  symbol: string;
  name: string;
  exchange: string;
  sector: string;
  industry: string;
  market_cap: number;
  price: number;
  change_pct: number;
  per: number;
  pbr: number;
  roe: number;
  revenue_growth: number;
  foreign_net_buy_5d: number;
  institution_net_buy_5d: number;
  supply_score: number;
  short_sale_ratio: number;
  momentum: number;
  strategy_score: number;
  rationale: string[];
  risk_flags: string[];
  trading_value_krw_100m: number;
  avg_volume_20d_10k: number;
  turnover_pct: number;
  psr: number;
  ev_ebitda: number;
  fcf_yield: number;
  dividend_yield: number;
  payout_ratio: number;
  dividend_growth: number;
  dividend_streak_years: number;
  dividend_stability_score: number;
  roa: number;
  operating_margin: number;
  net_margin: number;
  debt_ratio: number;
  current_ratio: number;
  eps_growth: number;
  operating_income_growth: number;
  beta: number;
  volatility_20d: number;
  drawdown_52w: number;
  rsi14: number;
  close_vs_ma20_pct: number;
  close_vs_ma60_pct: number;
  volume_surge: number;
  fair_value_upside: number;
  foreign_net_buy_20d: number;
  institution_net_buy_20d: number;
  pension_net_buy_20d: number;
  program_net_buy_5d: number;
  consecutive_foreign_buy_days: number;
  margin_debt_change_5d: number;
};

export type StrategyCandidateResponse = {
  run_id: number | null;
  run_at: string | null;
  strategy_code: string;
  strategy_name: string;
  source: string;
  data_freshness: DataFreshness;
  candidates: StrategyCandidateResult[];
};

export type DataFreshness = {
  latest_daily_price_date: string | null;
  expected_daily_price_date: string | null;
  daily_price_status: 'current' | 'stale' | 'missing' | 'unknown' | string;
  daily_price_providers: string[];
  latest_quote_snapshot_date: string | null;
  latest_supply_flow_date: string | null;
  latest_risk_indicator_date: string | null;
  latest_fundamental_period: string | null;
  message: string;
  warnings: string[];
};

export type ScreenerSearchRequest = {
  strategy_code?: string;
  formula?: string;
  limit?: number;
};

export type ScreenerSearchResponse = {
  strategy_code: string;
  strategy_name: string;
  source: string;
  data_freshness: DataFreshness;
  unsupported_conditions: string[];
  candidates: StrategyCandidateResult[];
};

export type UserStrategy = {
  id: number;
  code: string;
  name: string;
  summary: string;
  formula: string;
  result_count: number;
  created_at: string;
};

export type UserStrategyCreate = {
  name: string;
  summary: string;
  formula: string;
  result_count: number;
};

export type BacktestMetric = {
  label: string;
  value: string;
  tone: string;
};

export type EquityPoint = {
  day: string;
  value: number;
};

export type BacktestPreview = {
  strategy_code: string;
  period: string;
  assumptions: string[];
  metrics: BacktestMetric[];
  equity_curve: EquityPoint[];
};

export type BacktestRunRequest = {
  strategy_code: string;
  start_year: number;
  end_year: number;
  initial_amount: number;
  benchmark_code: string;
  rebalance_interval_months?: number;
  holding_count?: number;
};

export type BacktestPerformanceMetric = {
  metric: string;
  value: string;
};

export type BacktestAnnualReturn = {
  year: string;
  portfolio_return: number;
  yield_pct: number;
  balance: number;
  income: number;
};

export type BacktestEquityPoint = {
  label: string;
  portfolio: number;
};

export type BacktestBenchmarkPoint = {
  label: string;
  benchmark: number;
};

export type BacktestRebalanceRow = {
  date: string;
  holdings: string;
  entries: string;
  exits: string;
  turnover: string;
};

export type BacktestRunResult = {
  run_id: number | null;
  strategy_code: string;
  strategy_name: string;
  source: string;
  period: string;
  initial_amount: number;
  final_amount: number;
  run_at: string;
  notice: string;
  benchmark_code: string;
  benchmark_name: string;
  benchmark_curve: BacktestBenchmarkPoint[];
  backtest_policy: BacktestPolicy;
  metrics: BacktestPerformanceMetric[];
  annual_returns: BacktestAnnualReturn[];
  equity_curve: BacktestEquityPoint[];
  rebalance_history: BacktestRebalanceRow[];
};

export type BacktestRunSummary = {
  id: number;
  strategy_code: string;
  strategy_name: string;
  period: string;
  source: string;
  initial_amount: number;
  final_amount: number;
  created_at: string;
};

export type Dashboard = {
  as_of: string;
  modes: Array<{ code: string; label: string; enabled: boolean }>;
  strategies: Strategy[];
  recommendations: Recommendation[];
  backtest: BacktestPreview;
};

export type DataStatus = {
  connected: boolean;
  provider_status: Array<{ name: string; scope: string; status: string; ready: boolean }>;
  table_counts: Record<string, number>;
  message: string;
};

export type ManualDataRefreshRequest = {
  refresh_instruments?: boolean;
  refresh_daily_prices?: boolean;
  markets?: string[];
  lookback_days?: number;
};

export type ManualDataRefreshJob = {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | string;
  stage: string;
  progress_pct: number;
  current_step: number;
  total_steps: number;
  success_count: number;
  failed_count: number;
  saved_count: number;
  started_at: string;
  finished_at: string | null;
  elapsed_seconds: number;
  estimated_remaining_seconds: number | null;
  latest_daily_price_date: string | null;
  expected_daily_price_date: string | null;
  message: string;
  warnings: string[];
};

export type KisBrokerAccountStatus = {
  provider: string;
  ready: boolean;
  environment: string;
  account_configured: boolean;
  account_label: string;
  paper_trading_enabled: boolean;
  live_trading_enabled: boolean;
  message: string;
};

export type KisTradingSafetyStatus = {
  provider: string;
  ready: boolean;
  environment: string;
  account_label: string;
  paper_trading_enabled: boolean;
  live_trading_enabled: boolean;
  emergency_stop_enabled: boolean;
  manual_confirmation_required: boolean;
  daily_loss_stop_enabled: boolean;
  max_order_amount_krw: number;
  max_daily_order_count: number;
  max_daily_loss_krw: number;
  remaining_daily_order_count: number | null;
  can_submit_paper_orders: boolean;
  can_submit_live_orders: boolean;
  message: string;
  warnings: string[];
};

export type KisBrokerBalanceSummary = {
  deposit_amount: number;
  next_settlement_amount: number;
  purchase_amount: number;
  evaluation_amount: number;
  profit_loss_amount: number;
  profit_loss_rate: number;
  securities_evaluation_amount: number;
  total_evaluation_amount: number;
  net_asset_amount: number;
  total_loan_amount: number;
  previous_total_asset_evaluation_amount: number;
  asset_change_amount: number;
  asset_change_rate: number;
};

export type KisBrokerHolding = {
  symbol: string;
  name: string;
  trade_type: string;
  holding_quantity: number;
  orderable_quantity: number;
  average_price: number;
  purchase_amount: number;
  current_price: number;
  evaluation_amount: number;
  profit_loss_amount: number;
  profit_loss_rate: number;
  evaluation_earning_rate: number;
  change_rate: number;
};

export type KisBrokerBalance = {
  provider: string;
  environment: string;
  account_label: string;
  fetched_at: string;
  summary: KisBrokerBalanceSummary;
  holdings: KisBrokerHolding[];
};

export type KisBuyableCash = {
  provider: string;
  environment: string;
  symbol: string;
  orderable_cash: number;
  orderable_substitute: number;
  reusable_amount: number;
  calculation_unit_price: number;
  cash_buy_amount: number;
  cash_buy_quantity: number;
  max_buy_amount: number;
  max_buy_quantity: number;
  cma_evaluation_amount: number;
};

export type KisOrderExecutionItem = {
  order_date: string;
  order_time: string;
  order_branch_no: string;
  order_no: string;
  original_order_no: string;
  symbol: string;
  name: string;
  side_code: string;
  side_name: string;
  order_type_name: string;
  order_type_code: string;
  ordered_quantity: number;
  order_price: number;
  filled_quantity: number;
  average_price: number;
  filled_amount: number;
  remaining_quantity: number;
  rejected_quantity: number;
  canceled: boolean;
  status: string;
  execution_condition: string;
  exchange_code: string;
};

export type KisOrderExecutionSummary = {
  total_order_quantity: number;
  total_filled_quantity: number;
  total_filled_amount: number;
  estimated_fee_total: number;
  purchase_average_price: number;
};

export type KisOrderExecutions = {
  provider: string;
  environment: string;
  account_label: string;
  start_date: string;
  end_date: string;
  summary: KisOrderExecutionSummary;
  orders: KisOrderExecutionItem[];
};

export type KisOrderProposalLine = {
  symbol: string;
  name: string;
  side: 'buy' | 'sell';
  order_type: 'market' | 'limit';
  reference_price: number;
  quantity: number;
  estimated_amount: number;
  strategy_score: number;
  status: string;
  warnings: string[];
  rationale: string[];
};

export type KisOrderProposal = {
  provider: string;
  environment: string;
  account_label: string;
  proposal_id: string;
  generated_at: string;
  strategy_code: string;
  strategy_name: string;
  source: string;
  max_positions: number;
  amount_per_symbol: number;
  order_type: 'market' | 'limit';
  cash_buffer_rate: number;
  available_cash: number;
  cash_buffer_amount: number;
  total_estimated_amount: number;
  executable_count: number;
  warnings: string[];
  lines: KisOrderProposalLine[];
  audit_log_id: number | null;
};

export type KisOrderProposalRequest = {
  strategy_code: string;
  max_positions: number;
  amount_per_symbol: number;
  order_type?: 'market' | 'limit';
  cash_buffer_rate?: number;
};

export type KisPaperBatchOrderItem = {
  side?: 'buy' | 'sell';
  symbol: string;
  name?: string;
  quantity: number;
  order_type?: 'market' | 'limit';
  price?: number;
  exchange_id?: string;
};

export type KisPaperBatchOrderRequest = {
  orders: KisPaperBatchOrderItem[];
  confirm_submit: boolean;
  confirm_phrase: string;
};

export type KisPaperBatchOrderResult = {
  symbol: string;
  name: string;
  side: 'buy' | 'sell';
  order_type: 'market' | 'limit';
  quantity: number;
  price: number;
  estimated_amount: number;
  status: string;
  order_no: string;
  order_time: string;
  message: string;
};

export type KisPaperBatchOrderResponse = {
  provider: string;
  environment: string;
  account_label: string;
  batch_id: string;
  submitted_count: number;
  failed_count: number;
  total_estimated_amount: number;
  status: string;
  results: KisPaperBatchOrderResult[];
  before_audit_log_id: number | null;
  after_audit_log_id: number | null;
};

export type KisRealtimeQuoteStatus = {
  provider: string;
  environment: string;
  ws_url: string;
  running: boolean;
  connected: boolean;
  subscribed_symbols: string[];
  quote_count: number;
  last_message_at: string | null;
  last_error: string;
};

export type KisRealtimeQuote = {
  symbol: string;
  trade_time: string;
  price: number | null;
  change: number | null;
  change_rate: number | null;
  trade_volume: number | null;
  accumulated_volume: number | null;
  accumulated_trading_value: number | null;
  bid_price: number | null;
  ask_price: number | null;
  received_at: string;
  raw_tr_id: string;
};

export type YahooDailyPrice = {
  symbol: string;
  trade_date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  adjusted_close: number | null;
  volume: number | null;
  provider: string;
};

export type YahooDailyPricePreview = {
  provider: string;
  symbol: string;
  yahoo_symbol: string;
  exchange: string;
  count: number;
  prices: YahooDailyPrice[];
};

export type YahooDailyPriceImportRequest = {
  symbol: string;
  name?: string;
  exchange?: string;
  start?: string;
  end?: string;
  is_adjusted?: boolean;
};

export type YahooDailyPriceImportResult = {
  provider: string;
  job_id: number;
  symbol: string;
  yahoo_symbol: string;
  exchange: string;
  fetched_count: number;
  saved_count: number;
  message: string;
};

export type YahooDailyPriceBatchImportRequest = {
  strategy_code: string;
  start?: string;
  end?: string;
  max_symbols?: number;
  is_adjusted?: boolean;
};

export type YahooDailyPriceBatchImportItem = {
  symbol: string;
  name: string;
  exchange: string;
  status: string;
  saved_count: number;
  message: string;
};

export type YahooDailyPriceBatchImportResult = {
  provider: string;
  strategy_code: string;
  requested_symbols: number;
  success_count: number;
  failed_count: number;
  saved_count: number;
  items: YahooDailyPriceBatchImportItem[];
};

export async function fetchDashboard(): Promise<Dashboard> {
  const response = await fetch(`${API_BASE_URL}/api/dashboard`);

  if (!response.ok) {
    throw new Error(`대시보드 데이터를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchStrategyPerformance(refresh = false): Promise<StrategyPerformanceResponse[]> {
  const search = new URLSearchParams();
  if (refresh) search.set('refresh', 'true');
  const suffix = search.toString() ? `?${search}` : '';
  const response = await fetchWithTimeout(`${API_BASE_URL}/api/strategies/performance${suffix}`, {}, 45000);

  if (!response.ok) {
    throw new Error(`전략 성과 데이터를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchDataStatus(): Promise<DataStatus> {
  const response = await fetch(`${API_BASE_URL}/api/data/status`);

  if (!response.ok) {
    throw new Error(`데이터 상태를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function startManualDataRefresh(
  request: ManualDataRefreshRequest = {}
): Promise<ManualDataRefreshJob> {
  const response = await fetch(`${API_BASE_URL}/api/data/manual-refresh`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `최신 데이터 갱신을 시작하지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchManualDataRefreshJob(jobId: string): Promise<ManualDataRefreshJob> {
  const response = await fetch(`${API_BASE_URL}/api/data/manual-refresh/${jobId}`);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `최신 데이터 갱신 상태를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchKisBrokerAccountStatus(): Promise<KisBrokerAccountStatus> {
  const response = await fetch(`${API_BASE_URL}/api/broker/kis/account/status`);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 계좌 상태를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchKisTradingSafetyStatus(): Promise<KisTradingSafetyStatus> {
  const response = await fetch(`${API_BASE_URL}/api/broker/kis/safety-status`);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 주문 안전 상태를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchKisBrokerBalance(): Promise<KisBrokerBalance> {
  const response = await fetchWithTimeout(`${API_BASE_URL}/api/broker/kis/balance`, {}, 10000);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 잔고를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchKisOrderExecutions(): Promise<KisOrderExecutions> {
  const response = await fetchWithTimeout(`${API_BASE_URL}/api/broker/kis/orders`, {}, 10000);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 주문체결 내역을 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchKisBuyableCash(params: {
  symbol: string;
  order_price?: number;
  order_type?: 'market' | 'limit';
}): Promise<KisBuyableCash> {
  const search = new URLSearchParams();
  search.set('symbol', params.symbol);
  if (params.order_price !== undefined) search.set('order_price', String(params.order_price));
  if (params.order_type) search.set('order_type', params.order_type);

  const response = await fetchWithTimeout(`${API_BASE_URL}/api/broker/kis/buyable-cash?${search}`, {}, 10000);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 매수가능금액을 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function createKisOrderProposal(
  request: KisOrderProposalRequest
): Promise<KisOrderProposal> {
  const response = await fetchWithTimeout(
    `${API_BASE_URL}/api/broker/kis/order-proposals`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(request)
    },
    20000
  );

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 주문 제안을 생성하지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function submitKisPaperBatchOrders(
  request: KisPaperBatchOrderRequest
): Promise<KisPaperBatchOrderResponse> {
  const response = await fetch(`${API_BASE_URL}/api/broker/kis/paper/orders/batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 모의 일괄 주문을 제출하지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchKisRealtimeQuoteStatus(): Promise<KisRealtimeQuoteStatus> {
  const response = await fetch(`${API_BASE_URL}/api/data/kis/realtime/quotes/status`);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 실시간 시세 상태를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchKisRealtimeLatestQuotes(): Promise<KisRealtimeQuote[]> {
  const response = await fetch(`${API_BASE_URL}/api/data/kis/realtime/quotes/latest`);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 실시간 시세를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function subscribeKisRealtimeQuotes(symbols: string[]): Promise<KisRealtimeQuoteStatus> {
  const response = await fetch(`${API_BASE_URL}/api/data/kis/realtime/quotes/subscribe`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ symbols })
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 실시간 시세 구독을 시작하지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function unsubscribeKisRealtimeQuotes(symbols: string[]): Promise<KisRealtimeQuoteStatus> {
  const response = await fetch(`${API_BASE_URL}/api/data/kis/realtime/quotes/unsubscribe`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ symbols })
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 실시간 시세 구독을 해제하지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function stopKisRealtimeQuotes(): Promise<KisRealtimeQuoteStatus> {
  const response = await fetch(`${API_BASE_URL}/api/data/kis/realtime/quotes/stop`, {
    method: 'POST'
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 실시간 시세 연결을 종료하지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchYahooDailyPrices(params: {
  symbol: string;
  exchange?: string;
  start?: string;
  end?: string;
  limit?: number;
}): Promise<YahooDailyPricePreview> {
  const search = new URLSearchParams();
  search.set('symbol', params.symbol);
  if (params.exchange) search.set('exchange', params.exchange);
  if (params.start) search.set('start', params.start);
  if (params.end) search.set('end', params.end);
  if (params.limit) search.set('limit', String(params.limit));

  const response = await fetch(`${API_BASE_URL}/api/data/yahoo/daily-prices?${search}`);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `Yahoo 일봉 데이터를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function importYahooDailyPrices(
  request: YahooDailyPriceImportRequest
): Promise<YahooDailyPriceImportResult> {
  const response = await fetch(`${API_BASE_URL}/api/data/yahoo/daily-prices/import`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `Yahoo 일봉 데이터를 저장하지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function importYahooDailyPricesForStrategy(
  request: YahooDailyPriceBatchImportRequest
): Promise<YahooDailyPriceBatchImportResult> {
  const response = await fetch(`${API_BASE_URL}/api/data/yahoo/daily-prices/import/strategy`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `전략 후보의 Yahoo 일봉 데이터를 저장하지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchStrategyCandidates(
  strategyCode: string,
  refresh = false
): Promise<StrategyCandidateResponse> {
  // refresh=false: 후보 캐시 우선(데이터 기준일 불변 시 재계산 스킵). refresh=true: 수동 갱신(강제 재계산).
  const response = await fetchWithTimeout(
    `${API_BASE_URL}/api/strategies/${strategyCode}/candidates?refresh=${refresh}`,
    {},
    30000
  );

  if (!response.ok) {
    throw new Error(`전략 후보 종목을 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchStrategyExecutionContract(
  strategyCode: string
): Promise<StrategyExecutionContract> {
  const response = await fetch(`${API_BASE_URL}/api/strategies/${strategyCode}/contract`);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `전략 실행 계약을 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function searchScreener(
  request: ScreenerSearchRequest = {}
): Promise<ScreenerSearchResponse> {
  const response = await fetchWithTimeout(
    `${API_BASE_URL}/api/screener/search`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(request)
    },
    8000
  );

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `검색기 결과를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchUserStrategies(): Promise<UserStrategy[]> {
  const response = await fetch(`${API_BASE_URL}/api/user-strategies`);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `사용자 전략을 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function createUserStrategy(request: UserStrategyCreate): Promise<UserStrategy> {
  const response = await fetch(`${API_BASE_URL}/api/user-strategies`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `사용자 전략을 저장하지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function deleteUserStrategy(strategyCode: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/user-strategies/${strategyCode}`, {
    method: 'DELETE'
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `사용자 전략을 삭제하지 못했습니다. (${response.status})`);
  }
}

export async function fetchBacktestRuns(limit = 10): Promise<BacktestRunSummary[]> {
  const response = await fetch(`${API_BASE_URL}/api/backtests/runs?limit=${limit}`);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `최근 백테스트 결과를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchBacktestRun(runId: number): Promise<BacktestRunResult> {
  const response = await fetch(`${API_BASE_URL}/api/backtests/runs/${runId}`);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `저장된 백테스트 결과를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function runBacktest(request: BacktestRunRequest): Promise<BacktestRunResult> {
  const response = await fetch(`${API_BASE_URL}/api/backtests/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `백테스트를 실행하지 못했습니다. (${response.status})`);
  }

  return response.json();
}

async function readErrorDetail(response: Response) {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail ?? '';
  } catch {
    return '';
  }
}
