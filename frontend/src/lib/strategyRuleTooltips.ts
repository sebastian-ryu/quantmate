export type StrategyRuleGroup = 'signal' | 'ranking' | 'risk';
export type RiskRuleAction = 'exclude' | 'deduct' | 'notice';

type RuleDescription = {
  keywords: string[];
  description: string;
};

const signalDescriptions: RuleDescription[] = [
  {
    keywords: ['검색기', '조건식'],
    description: '검색기에서 저장한 조건식을 후보 종목 필터로 사용합니다. 사용자가 만든 조건이 실제 전략 후보군의 출발점이 됩니다.'
  },
  {
    keywords: ['3~12개월', '수익률'],
    description: '최근 중기 구간에서 시장이나 후보군 대비 강한 가격 흐름을 보인 종목을 우선 후보로 봅니다.'
  },
  {
    keywords: ['1개월', '급등'],
    description: '최근 1개월에 과도하게 오른 종목은 단기 과열 가능성이 있어 점수를 낮춥니다.'
  },
  {
    keywords: ['20일', '60일', '이동평균'],
    description: '현재 가격이 주요 이동평균 위에 있는지 확인해 상승 추세가 유지되는 종목을 찾습니다.'
  },
  {
    keywords: ['거래대금'],
    description: '거래대금이 충분한 종목을 우선해 실제 매수와 매도 시 체결 부담을 줄입니다.'
  },
  {
    keywords: ['ROE'],
    description: '자기자본 대비 이익 창출력이 높은 기업을 선호합니다. 수익성이 좋은 기업을 찾는 조건입니다.'
  },
  {
    keywords: ['PER'],
    description: '이익 대비 주가 수준을 확인합니다. 낮은 PER은 이익 대비 저평가 가능성을 의미할 수 있습니다.'
  },
  {
    keywords: ['PBR'],
    description: '순자산 대비 주가 수준을 확인합니다. 낮은 PBR은 자산가치 대비 저평가 가능성을 의미할 수 있습니다.'
  },
  {
    keywords: ['매출', '성장'],
    description: '매출이나 이익이 빠르게 늘어나는 기업을 찾습니다. 성장주 전략에서 특히 중요한 조건입니다.'
  },
  {
    keywords: ['외국인', '기관', '수급'],
    description: '외국인과 기관의 순매수 흐름을 확인해 큰 자금이 들어오는 종목을 찾습니다.'
  },
  {
    keywords: ['공매도', '신용'],
    description: '공매도나 신용잔고 부담이 큰 종목은 단기 하락 압력이나 변동성 확대 가능성이 있어 주의합니다.'
  },
  {
    keywords: ['변동성', '낙폭'],
    description: '가격 변동 폭과 최근 고점 대비 하락 폭을 확인해 손실 위험이 과도한 종목을 걸러냅니다.'
  },
  {
    keywords: ['배당'],
    description: '배당수익률과 배당 안정성을 확인해 현금흐름이 있는 방어형 후보를 찾습니다.'
  }
];

const rankingDescriptions: RuleDescription[] = [
  {
    keywords: ['상대수익률'],
    description: '시장이나 후보군보다 더 강하게 오른 종목을 높은 순위에 둡니다.'
  },
  {
    keywords: ['거래대금'],
    description: '거래가 활발한 종목을 높은 순위에 둬 실제 매매 가능성을 높입니다.'
  },
  {
    keywords: ['추세'],
    description: '상승 추세가 안정적으로 이어지는 종목을 높은 순위에 둡니다.'
  },
  {
    keywords: ['과열'],
    description: '단기 급등으로 과열된 종목은 추격 매수 위험이 있어 순위를 낮춥니다.'
  },
  {
    keywords: ['ROE', '수익성'],
    description: '수익성이 높은 기업을 높은 순위에 둡니다.'
  },
  {
    keywords: ['밸류', '저평가', 'PER', 'PBR'],
    description: '이익이나 자산가치 대비 가격 부담이 낮은 종목을 높은 순위에 둡니다.'
  },
  {
    keywords: ['수급', '외국인', '기관'],
    description: '큰 자금의 매수 흐름이 강한 종목을 높은 순위에 둡니다.'
  },
  {
    keywords: ['성장'],
    description: '매출과 이익 성장성이 높은 종목을 높은 순위에 둡니다.'
  }
];

const riskDescriptions: RuleDescription[] = [
  {
    keywords: ['급등', '추격'],
    description: '급등 직후 매수하면 단기 조정에 노출될 수 있어 전략 점수나 진입 우선순위를 낮추는 성격입니다.'
  },
  {
    keywords: ['시장 급락'],
    description: '시장 전체가 급락하는 구간에서는 개별 종목 신호의 성공률도 낮아질 수 있어 신규 진입을 보수적으로 판단해야 합니다.'
  },
  {
    keywords: ['거래량 급감'],
    description: '거래량이 줄면 신호 신뢰도가 낮아지고 매도 시 체결 부담이 커져 후보 제외 기준으로 사용합니다.'
  },
  {
    keywords: ['공매도'],
    description: '공매도 비중이 높으면 단기 하락 압력이나 변동성이 커질 수 있습니다.'
  },
  {
    keywords: ['가치 함정'],
    description: '저평가처럼 보이지만 실적 악화나 구조적 문제로 주가가 회복되지 않을 수 있어 추가 확인이 필요한 신호입니다.'
  },
  {
    keywords: ['실적 악화'],
    description: '최근 실적 흐름이 나빠진 종목은 저평가 조건을 만족해도 후보에서 제외하는 성격입니다.'
  },
  {
    keywords: ['재무 데이터 업데이트', '재무 데이터'],
    description: '재무 데이터가 늦게 반영되면 현재 상태와 화면의 지표가 다를 수 있어 자동 제외보다는 주의 표시로 봅니다.'
  },
  {
    keywords: ['고PER', 'PER'],
    description: '밸류에이션이 높은 종목은 실적 기대가 꺾일 때 하락 폭이 커질 수 있습니다.'
  },
  {
    keywords: ['고평가'],
    description: '성장 기대가 이미 가격에 많이 반영된 종목은 실적 실망 시 하락 폭이 커질 수 있어 주의 표시로 봅니다.'
  },
  {
    keywords: ['돌파 실패'],
    description: '돌파 후 가격이 다시 기준선 아래로 내려오면 신호가 무효화된 것으로 보고 후보에서 제외하는 성격입니다.'
  },
  {
    keywords: ['약세장'],
    description: '시장 추세가 약할 때는 돌파나 성장 신호의 성공률이 낮아질 수 있어 신호 품질을 낮게 평가합니다.'
  },
  {
    keywords: ['박스권', '속임수'],
    description: '박스권에서는 일시적 돌파가 다시 되돌려질 가능성이 높아 전략 점수나 진입 우선순위를 낮춥니다.'
  },
  {
    keywords: ['과열'],
    description: '단기 가격이나 변동성이 이미 과열된 구간이면 추격 매수 위험이 있어 전략 점수나 진입 우선순위를 낮춥니다.'
  },
  {
    keywords: ['갭', '보류'],
    description: '가격이 큰 갭으로 급등한 경우 체결 가격이 불리할 수 있어 신규 진입을 보류하는 성격입니다.'
  },
  {
    keywords: ['수급 데이터'],
    description: '수급 데이터가 늦게 반영되면 현재 매수세와 화면 지표가 다를 수 있어 자동 제외보다는 주의 표시로 봅니다.'
  },
  {
    keywords: ['뉴스성', '단기 수급'],
    description: '뉴스로 생긴 일시적 매수세는 되돌림이 빠를 수 있어 전략 점수나 우선순위를 낮춥니다.'
  },
  {
    keywords: ['매수세', '반전'],
    description: '외국인이나 기관 매수세가 매도로 바뀌면 수급 신호가 무효화된 것으로 보고 후보에서 제외하는 성격입니다.'
  },
  {
    keywords: ['상승장', '소외'],
    description: '저변동성 전략은 강한 상승장에서 시장 상승을 충분히 따라가지 못할 수 있어 기대수익 측면의 주의 신호입니다.'
  },
  {
    keywords: ['손절', '청산', '낙폭', 'MDD'],
    description: '손실이 커지기 전에 포지션을 줄이거나 제외하는 운용 규칙이 필요하다는 의미입니다.'
  },
  {
    keywords: ['유동성', '거래대금'],
    description: '유동성이 낮은 종목은 주문 체결과 가격 충격 위험이 커질 수 있습니다.'
  },
  {
    keywords: ['전략 편집', '확장 예정'],
    description: '사용자 등록 전략의 위험 조건은 아직 자동 판정 규칙으로 완전히 정의되지 않았고, 현재는 참고 설명으로 표시합니다.'
  }
];

const fallbackDescriptions: Record<StrategyRuleGroup, string> = {
  signal: '후보 조건은 전략이 어떤 종목을 검색 대상으로 삼을지 결정하는 1차 필터입니다.',
  ranking: '우선순위는 후보 종목 중 어떤 종목을 더 높은 순위로 볼지 결정하는 정렬 기준입니다.',
  risk: '위험 제어는 매매 손실이나 과도한 변동성을 줄이기 위해 감점하거나 제외하는 기준입니다.'
};

export function describeStrategyRule(rule: string, group: StrategyRuleGroup) {
  const normalizedRule = normalizeRule(rule);
  const descriptions = {
    signal: signalDescriptions,
    ranking: rankingDescriptions,
    risk: riskDescriptions
  }[group];

  const matched = descriptions.find((item) =>
    item.keywords.some((keyword) => normalizedRule.includes(keyword.toLowerCase()))
  );

  return matched?.description ?? fallbackDescriptions[group];
}

export function classifyRiskRule(rule: string): RiskRuleAction {
  const normalizedRule = normalizeRule(rule);

  if (hasKeyword(normalizedRule, ['제외', '보류'])) {
    return 'exclude';
  }

  if (hasKeyword(normalizedRule, ['감점', '순위 하락', '점수 하락'])) {
    return 'deduct';
  }

  return 'notice';
}

export function riskRuleActionLabel(rule: string) {
  const action = classifyRiskRule(rule);

  if (action === 'exclude') return '제외/보류';
  if (action === 'deduct') return '감점';
  return '주의';
}

export function riskRuleActionDescription(rule: string) {
  const action = classifyRiskRule(rule);

  if (action === 'exclude') {
    return '조건이 확인되면 후보 종목에서 제외하거나 신규 진입을 보류하는 기준입니다.';
  }

  if (action === 'deduct') {
    return '후보에는 남길 수 있지만 전략 점수나 우선순위를 낮추는 기준입니다.';
  }

  return '자동 제외 조건이라기보다 전략 운용 전에 확인해야 하는 위험 신호입니다.';
}

function normalizeRule(rule: string) {
  return rule.replace(/\s+/g, ' ').toLowerCase();
}

function hasKeyword(value: string, keywords: string[]) {
  return keywords.some((keyword) => value.includes(keyword.toLowerCase()));
}
