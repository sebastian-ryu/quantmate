export type StrategyRuleGroup = 'signal' | 'ranking' | 'risk';

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
    description: '급등 직후 매수하면 단기 조정에 노출될 수 있어 진입 가격과 시점을 더 보수적으로 봅니다.'
  },
  {
    keywords: ['시장', '급락'],
    description: '시장 전체가 급락하는 구간에서는 개별 종목 신호의 성공률도 낮아질 수 있어 방어 규칙이 필요합니다.'
  },
  {
    keywords: ['거래량', '급감'],
    description: '거래량이 줄면 신호 신뢰도가 낮아지고 매도 시 체결 부담이 커질 수 있습니다.'
  },
  {
    keywords: ['공매도'],
    description: '공매도 비중이 높으면 단기 하락 압력이나 변동성이 커질 수 있습니다.'
  },
  {
    keywords: ['고PER', 'PER'],
    description: '밸류에이션이 높은 종목은 실적 기대가 꺾일 때 하락 폭이 커질 수 있습니다.'
  },
  {
    keywords: ['손절', '낙폭', 'MDD'],
    description: '손실이 커지기 전에 포지션을 줄이거나 제외해 포트폴리오 전체 손실을 제한합니다.'
  },
  {
    keywords: ['유동성', '거래대금'],
    description: '유동성이 낮은 종목은 주문 체결과 가격 충격 위험이 커질 수 있습니다.'
  }
];

const fallbackDescriptions: Record<StrategyRuleGroup, string> = {
  signal: '후보 조건은 전략이 어떤 종목을 검색 대상으로 삼을지 결정하는 1차 필터입니다.',
  ranking: '우선순위는 후보 종목 중 어떤 종목을 더 높은 순위로 볼지 결정하는 정렬 기준입니다.',
  risk: '위험 제어는 매매 손실이나 과도한 변동성을 줄이기 위해 감점하거나 제외하는 기준입니다.'
};

export function describeStrategyRule(rule: string, group: StrategyRuleGroup) {
  const normalizedRule = rule.replace(/\s+/g, ' ').toLowerCase();
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
