import { env } from '$env/dynamic/public';

const API_BASE_URL = env.PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

export type Strategy = {
  code: string;
  name: string;
  style: string;
  summary: string;
  data_requirements: string[];
  risk_notes: string[];
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

export type PaperConfig = {
  enabled: boolean;
  initial_cash: number;
  max_order_amount: number;
  daily_order_limit: number;
  daily_loss_limit: number;
  fill_model: string;
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

export async function fetchPaperConfig(): Promise<PaperConfig> {
  const response = await fetch(`${API_BASE_URL}/api/paper/config`);

  if (!response.ok) {
    throw new Error(`모의 투자 설정을 불러오지 못했습니다. (${response.status})`);
  }

  return response.json();
}

export async function updatePaperConfig(enabled: boolean): Promise<PaperConfig> {
  const response = await fetch(`${API_BASE_URL}/api/paper/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled })
  });

  if (!response.ok) {
    throw new Error(`모의 투자 설정을 저장하지 못했습니다. (${response.status})`);
  }

  return response.json();
}
