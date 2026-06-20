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
};

export type StrategyCandidateResponse = {
  strategy_code: string;
  strategy_name: string;
  source: string;
  candidates: StrategyCandidateResult[];
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

export async function fetchStrategyCandidates(
  strategyCode: string
): Promise<StrategyCandidateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/strategies/${strategyCode}/candidates`);

  if (!response.ok) {
    throw new Error(`전략 후보 종목을 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}
