export type StrategyDraft = {
  id: string;
  name: string;
  summary: string;
  resultCount: number;
  formula: string;
  createdAt: string;
};

export const STRATEGY_DRAFTS_STORAGE_KEY = 'quantmate.strategyDrafts';

function canUseLocalStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function isStrategyDraft(value: unknown): value is StrategyDraft {
  if (!value || typeof value !== 'object') return false;

  const draft = value as Partial<StrategyDraft>;
  return (
    typeof draft.id === 'string' &&
    typeof draft.name === 'string' &&
    typeof draft.summary === 'string' &&
    typeof draft.resultCount === 'number' &&
    typeof draft.formula === 'string' &&
    typeof draft.createdAt === 'string'
  );
}

export function loadStrategyDrafts() {
  if (!canUseLocalStorage()) return [];

  try {
    const rawValue = window.localStorage.getItem(STRATEGY_DRAFTS_STORAGE_KEY);
    if (!rawValue) return [];

    const parsed = JSON.parse(rawValue);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter(isStrategyDraft);
  } catch {
    return [];
  }
}

export function saveStrategyDrafts(drafts: StrategyDraft[]) {
  if (!canUseLocalStorage()) return;

  window.localStorage.setItem(STRATEGY_DRAFTS_STORAGE_KEY, JSON.stringify(drafts));
}
