import { env } from '$env/dynamic/public';

const API_BASE_URL = env.PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

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
  default_enabled: boolean;
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
  strategy_code: string;
  strategy_name: string;
  source: string;
  candidates: StrategyCandidateResult[];
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

export async function fetchDataStatus(): Promise<DataStatus> {
  const response = await fetch(`${API_BASE_URL}/api/data/status`);

  if (!response.ok) {
    throw new Error(`데이터 상태를 불러오지 못했습니다. (${response.status})`);
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

export async function fetchKisBrokerBalance(): Promise<KisBrokerBalance> {
  const response = await fetch(`${API_BASE_URL}/api/broker/kis/balance`);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 잔고를 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function fetchKisOrderExecutions(): Promise<KisOrderExecutions> {
  const response = await fetch(`${API_BASE_URL}/api/broker/kis/orders`);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `KIS 주문체결 내역을 불러오지 못했습니다. (${response.status})`);
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
  strategyCode: string
): Promise<StrategyCandidateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/strategies/${strategyCode}/candidates`);

  if (!response.ok) {
    throw new Error(`전략 후보 종목을 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function searchScreener(
  request: ScreenerSearchRequest = {}
): Promise<ScreenerSearchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/screener/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(request)
  });

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
