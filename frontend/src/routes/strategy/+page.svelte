<script lang="ts">
  import { onMount, tick } from 'svelte';
  import {
    createKisOrderProposal,
    fetchDashboard,
    fetchKisBuyableCash,
    fetchKisBrokerAccountStatus,
    fetchKisBrokerBalance,
    fetchKisOrderExecutions,
    fetchStrategyCandidates,
    type Dashboard,
    type KisBuyableCash,
    type KisBrokerAccountStatus,
    type KisBrokerBalance,
    type KisOrderProposal,
    type KisPaperBatchOrderResponse,
    type KisOrderExecutions,
    type Strategy,
    type StrategyCandidateResult,
    submitKisPaperBatchOrders,
    fetchUserStrategies,
    type UserStrategy
  } from '$lib/api';
  import { describeStrategyRule } from '$lib/strategyRuleTooltips';

  type StrategyOption = {
    code: string;
    name: string;
    style: string;
    category: string;
    holdingPeriod: string;
    rebalanceRule: string;
    source: string;
    sourceKind: 'system' | 'custom';
    summary: string;
    dataRequirements: string[];
    universeFilter: string[];
    signalRules: string[];
    rankingRules: string[];
    riskControls: string[];
    riskNotes: string[];
    backtestAssumptions: string[];
    references: string[];
    formula?: string;
    resultCount?: number;
  };

  type StrategyCandidate = {
    symbol: string;
    name: string;
    exchange: string;
    sector: string;
    industry: string;
    marketCap: number;
    price: number;
    changePct: number;
    per: number;
    pbr: number;
    roe: number;
    revenueGrowth: number;
    foreignNetBuy5d: number;
    institutionNetBuy5d: number;
    supplyScore: number;
    shortSaleRatio: number;
    momentum: number;
    strategyScore: number;
    rationale: string[];
    riskFlags: string[];
  };

  type CandidateUniverseRow = Omit<StrategyCandidate, 'strategyScore' | 'rationale' | 'riskFlags'>;

  let dashboard: Dashboard | null = null;
  let selectedStrategy = 'relative-momentum-swing';
  let registeredStrategies: UserStrategy[] = [];
  let candidateRows: StrategyCandidate[] = [];
  let candidateSource = '';
  let candidatesLoading = false;
  let candidatesError = '';
  let candidateRequestId = 0;
  let brokerStatus: KisBrokerAccountStatus | null = null;
  let brokerBalance: KisBrokerBalance | null = null;
  let brokerOrders: KisOrderExecutions | null = null;
  let brokerLoading = false;
  let brokerError = '';
  let brokerOrderError = '';
  let buyableSymbol = '005930';
  let buyableOrderType: 'market' | 'limit' = 'market';
  let buyablePrice = 0;
  let buyableLoading = false;
  let buyableError = '';
  let buyableResult: KisBuyableCash | null = null;
  let proposalMaxPositions = 10;
  let proposalAmountPerSymbol = 5000000;
  let proposalOrderType: 'market' | 'limit' = 'market';
  let proposalCashBufferRate = 0;
  let orderProposal: KisOrderProposal | null = null;
  let selectedProposalSymbols: string[] = [];
  let batchConfirmPhrase = '';
  let batchSubmitting = false;
  let batchSubmitError = '';
  let batchSubmitResult: KisPaperBatchOrderResponse | null = null;
  let proposalLoading = false;
  let proposalError = '';
  let loading = true;
  let error = '';

  const candidateColumns = [
    { label: '종목', description: '종목명, 종목코드, 업종을 함께 표시합니다.' },
    { label: '전략 점수', description: '선택한 전략의 조건을 종합해 0~100점으로 환산한 순위 점수입니다.' },
    { label: '선정 사유', description: '해당 종목이 전략 후보로 선정된 핵심 근거와 위험 신호입니다.' },
    { label: '거래소', description: '종목이 상장된 시장입니다. KOSPI, KOSDAQ 등을 표시합니다.' },
    { label: '섹터', description: '종목의 큰 산업 분류입니다.' },
    { label: '시가총액', description: '상장주식 가치의 총합입니다. 현재 화면은 조 단위로 표시합니다.' },
    { label: '가격', description: '후보 산출에 사용한 최근 가격 또는 현재가입니다.' },
    { label: '등락', description: '최근 가격 기준 등락률입니다. 양수는 상승, 음수는 하락입니다.' },
    { label: 'PER', description: '주가를 주당순이익으로 나눈 값입니다. 낮을수록 이익 대비 주가가 낮게 평가될 수 있습니다.' },
    { label: 'PBR', description: '주가를 주당순자산으로 나눈 값입니다. 낮을수록 순자산 대비 주가가 낮게 평가될 수 있습니다.' },
    { label: 'ROE', description: '자기자본이익률입니다. 자본 대비 이익 창출력을 나타냅니다.' },
    { label: '성장', description: '매출 성장률입니다. 높을수록 외형 성장 속도가 빠릅니다.' },
    { label: '외국인 5일', description: '최근 5거래일 외국인 순매수 금액입니다. 억 원 단위로 표시합니다.' },
    { label: '기관 5일', description: '최근 5거래일 기관 순매수 금액입니다. 억 원 단위로 표시합니다.' },
    { label: '수급 점수', description: '외국인, 기관, 거래대금 흐름 등을 종합한 수급 강도 점수입니다.' },
    { label: '공매도', description: '거래대금 대비 공매도 비중입니다. 높을수록 단기 수급 부담이 커질 수 있습니다.' },
    { label: '모멘텀', description: '최근 수익률과 추세 강도를 종합한 가격 흐름 점수입니다.' }
  ];

  const candidateUniverse: CandidateUniverseRow[] = [
    {
      symbol: '005930',
      name: '삼성전자',
      exchange: 'KOSPI',
      sector: '기술',
      industry: '반도체',
      marketCap: 2247.7,
      price: 354000,
      changePct: -2.3,
      per: 14.8,
      pbr: 1.4,
      roe: 9.8,
      revenueGrowth: 8.4,
      foreignNetBuy5d: 1260,
      institutionNetBuy5d: 820,
      supplyScore: 86,
      shortSaleRatio: 3.1,
      momentum: 82
    },
    {
      symbol: '000660',
      name: 'SK하이닉스',
      exchange: 'KOSPI',
      sector: '기술',
      industry: '반도체',
      marketCap: 1957.7,
      price: 276400,
      changePct: 2.9,
      per: 18.3,
      pbr: 1.6,
      roe: 12.2,
      revenueGrowth: 17.2,
      foreignNetBuy5d: 2480,
      institutionNetBuy5d: 1120,
      supplyScore: 91,
      shortSaleRatio: 4.9,
      momentum: 78
    },
    {
      symbol: '035720',
      name: '카카오',
      exchange: 'KOSPI',
      sector: '커뮤니케이션',
      industry: '인터넷 서비스',
      marketCap: 23.4,
      price: 43750,
      changePct: 1.2,
      per: 27.4,
      pbr: 1.1,
      roe: 4.5,
      revenueGrowth: 3.1,
      foreignNetBuy5d: 180,
      institutionNetBuy5d: 260,
      supplyScore: 58,
      shortSaleRatio: 6.2,
      momentum: 71
    },
    {
      symbol: '005380',
      name: '현대차',
      exchange: 'KOSPI',
      sector: '소비순환재',
      industry: '자동차',
      marketCap: 138.6,
      price: 613000,
      changePct: 2.0,
      per: 6.2,
      pbr: 0.8,
      roe: 12.8,
      revenueGrowth: 9.5,
      foreignNetBuy5d: 610,
      institutionNetBuy5d: 420,
      supplyScore: 77,
      shortSaleRatio: 2.8,
      momentum: 74
    },
    {
      symbol: '035420',
      name: 'NAVER',
      exchange: 'KOSPI',
      sector: '커뮤니케이션',
      industry: '인터넷 서비스',
      marketCap: 31.2,
      price: 194500,
      changePct: -0.6,
      per: 22.7,
      pbr: 1.3,
      roe: 6.1,
      revenueGrowth: 7.4,
      foreignNetBuy5d: 360,
      institutionNetBuy5d: 190,
      supplyScore: 64,
      shortSaleRatio: 5.1,
      momentum: 66
    },
    {
      symbol: '247540',
      name: '에코프로비엠',
      exchange: 'KOSDAQ',
      sector: '소재',
      industry: '전지 소재',
      marketCap: 12.8,
      price: 132400,
      changePct: 4.1,
      per: 42.5,
      pbr: 3.8,
      roe: 8.4,
      revenueGrowth: 19.8,
      foreignNetBuy5d: 210,
      institutionNetBuy5d: 340,
      supplyScore: 69,
      shortSaleRatio: 7.4,
      momentum: 83
    },
    {
      symbol: '068270',
      name: '셀트리온',
      exchange: 'KOSPI',
      sector: '헬스케어',
      industry: '바이오',
      marketCap: 41.5,
      price: 188600,
      changePct: 1.5,
      per: 31.6,
      pbr: 2.2,
      roe: 7.6,
      revenueGrowth: 11.9,
      foreignNetBuy5d: 520,
      institutionNetBuy5d: 780,
      supplyScore: 79,
      shortSaleRatio: 3.9,
      momentum: 76
    },
    {
      symbol: '012450',
      name: '한화에어로스페이스',
      exchange: 'KOSPI',
      sector: '산업재',
      industry: '방산',
      marketCap: 15.7,
      price: 315000,
      changePct: 3.8,
      per: 19.4,
      pbr: 2.5,
      roe: 14.2,
      revenueGrowth: 24.3,
      foreignNetBuy5d: 840,
      institutionNetBuy5d: 960,
      supplyScore: 88,
      shortSaleRatio: 2.2,
      momentum: 89
    },
    {
      symbol: '105560',
      name: 'KB금융',
      exchange: 'KOSPI',
      sector: '금융',
      industry: '은행',
      marketCap: 34.1,
      price: 84600,
      changePct: 0.8,
      per: 5.4,
      pbr: 0.6,
      roe: 10.9,
      revenueGrowth: 5.7,
      foreignNetBuy5d: 430,
      institutionNetBuy5d: 510,
      supplyScore: 73,
      shortSaleRatio: 1.7,
      momentum: 68
    },
    {
      symbol: '051910',
      name: 'LG화학',
      exchange: 'KOSPI',
      sector: '소재',
      industry: '화학',
      marketCap: 25.6,
      price: 362000,
      changePct: -1.1,
      per: 16.8,
      pbr: 0.9,
      roe: 5.6,
      revenueGrowth: 2.4,
      foreignNetBuy5d: -120,
      institutionNetBuy5d: 160,
      supplyScore: 55,
      shortSaleRatio: 5.7,
      momentum: 52
    },
    {
      symbol: '086790',
      name: '하나금융지주',
      exchange: 'KOSPI',
      sector: '금융',
      industry: '은행',
      marketCap: 18.9,
      price: 64200,
      changePct: 1.0,
      per: 4.9,
      pbr: 0.5,
      roe: 11.7,
      revenueGrowth: 4.8,
      foreignNetBuy5d: 390,
      institutionNetBuy5d: 350,
      supplyScore: 70,
      shortSaleRatio: 1.4,
      momentum: 63
    },
    {
      symbol: '034020',
      name: '두산에너빌리티',
      exchange: 'KOSPI',
      sector: '산업재',
      industry: '전력설비',
      marketCap: 13.8,
      price: 21500,
      changePct: 2.6,
      per: 28.1,
      pbr: 1.8,
      roe: 6.8,
      revenueGrowth: 13.6,
      foreignNetBuy5d: 280,
      institutionNetBuy5d: 230,
      supplyScore: 67,
      shortSaleRatio: 4.4,
      momentum: 80
    }
  ];

  onMount(async () => {
    try {
      const [dashboardData, userStrategies] = await Promise.all([
        fetchDashboard(),
        fetchUserStrategies()
      ]);
      dashboard = dashboardData;
      registeredStrategies = userStrategies;
      selectedStrategy = dashboard.backtest.strategy_code;
      loading = false;
      await tick();
      void loadCandidateRowsForSelectedStrategy();
      void loadBrokerAccount();
    } catch (err) {
      error = err instanceof Error ? err.message : '전략 데이터를 불러오지 못했습니다.';
      loading = false;
    }
  });

  $: baseStrategies = dashboard?.strategies ?? [];
  $: strategyOptions = [
    ...baseStrategies.map(toBaseStrategyOption),
    ...registeredStrategies.map(toDraftStrategyOption)
  ];
  $: systemStrategyOptions = strategyOptions.filter((item) => item.sourceKind === 'system');
  $: customStrategyOptions = strategyOptions.filter((item) => item.sourceKind === 'custom');
  $: selectedOption =
    strategyOptions.find((item) => item.code === selectedStrategy) ?? strategyOptions[0] ?? null;
  $: averageScore = candidateRows.length
    ? Math.round(candidateRows.reduce((total, item) => total + item.strategyScore, 0) / candidateRows.length)
    : 0;
  $: executableProposalLines = (orderProposal?.lines ?? []).filter((line) => line.status === '주문 가능');
  $: selectedProposalLines = executableProposalLines.filter((line) =>
    selectedProposalSymbols.includes(line.symbol)
  );
  $: selectedProposalAmount = selectedProposalLines.reduce(
    (total, line) => total + line.estimated_amount,
    0
  );
  $: canSubmitBatchOrders =
    Boolean(brokerStatus?.paper_trading_enabled) &&
    selectedProposalLines.length > 0 &&
    batchConfirmPhrase.trim() === '모의주문 실행' &&
    !batchSubmitting;

  function toBaseStrategyOption(strategy: Strategy): StrategyOption {
    return {
      code: strategy.code,
      name: strategy.name,
      style: strategy.style,
      category: strategy.category ?? strategy.style,
      holdingPeriod: strategy.holding_period ?? strategy.style,
      rebalanceRule: strategy.rebalance_rule ?? '전략 기본 규칙 사용',
      source: '기본 제공 전략',
      sourceKind: strategy.source_type === 'user' ? 'custom' : 'system',
      summary: strategy.summary,
      dataRequirements: strategy.data_requirements ?? [],
      universeFilter: strategy.universe_filter ?? [],
      signalRules: strategy.signal_rules ?? [],
      rankingRules: strategy.ranking_rules ?? [],
      riskControls: strategy.risk_controls ?? [],
      riskNotes: strategy.risk_notes ?? [],
      backtestAssumptions: strategy.backtest_assumptions ?? [],
      references: strategy.references ?? []
    };
  }

  function toDraftStrategyOption(strategy: UserStrategy): StrategyOption {
    return {
      code: strategy.code,
      name: strategy.name,
      style: '검색식 기반',
      category: '사용자 조건식',
      holdingPeriod: '백테스트 조건에서 지정',
      rebalanceRule: '백테스트 단계에서 지정',
      source: '검색기 등록 전략',
      sourceKind: 'custom',
      summary: strategy.summary,
      dataRequirements: ['검색기 조건식', '검색 결과 후보군', '백테스트용 가격 데이터'],
      universeFilter: ['검색기에서 선택한 누적 조건'],
      signalRules: [strategy.formula],
      rankingRules: ['저장 조건식으로 후보를 필터링한 뒤 실제 일봉 기반 점수로 정렬'],
      riskControls: ['리스크 조건은 전략 편집 기능에서 확장 예정'],
      riskNotes: ['현재는 검색식 기반 전략 초안'],
      backtestAssumptions: ['검색식 결과를 후보군으로 사용', '리밸런싱 주기는 백테스트 조건에서 지정 예정'],
      references: [],
      formula: strategy.formula,
      resultCount: strategy.result_count
    };
  }

  function strategyLabel(item: StrategyOption) {
    return `${item.name} · ${item.style}`;
  }

  function sourceBadgeLabel(item: StrategyOption) {
    return item.sourceKind === 'system' ? '시스템 제공' : '사용자 등록';
  }

  function backtestHref(item: StrategyOption) {
    return `/strategies?strategy=${encodeURIComponent(item.code)}`;
  }

  function firstRules(rules: string[] | undefined) {
    return (rules ?? []).filter(Boolean).slice(0, 4);
  }

  async function handleStrategyChange() {
    orderProposal = null;
    selectedProposalSymbols = [];
    batchConfirmPhrase = '';
    batchSubmitError = '';
    batchSubmitResult = null;
    proposalError = '';
    await loadCandidateRowsForSelectedStrategy();
  }

  async function loadCandidateRowsForSelectedStrategy() {
    await tick();
    await loadCandidateRows(selectedOption);
  }

  async function loadCandidateRows(option: StrategyOption | null) {
    const requestId = candidateRequestId + 1;
    candidateRequestId = requestId;
    candidatesError = '';

    if (!option) {
      candidateRows = [];
      candidateSource = '';
      return;
    }

    candidatesLoading = true;

    try {
      const response = await fetchStrategyCandidates(option.code);
      if (candidateRequestId !== requestId) return;
      candidateRows = response.candidates.map(toStrategyCandidate);
      if (!buyableSymbol && candidateRows[0]?.symbol) buyableSymbol = candidateRows[0].symbol;
      candidateSource = response.source;
    } catch (err) {
      if (candidateRequestId !== requestId) return;
      candidatesError = err instanceof Error ? err.message : '전략 후보 종목을 불러오지 못했습니다.';
      candidateRows = [];
      candidateSource = '';
    } finally {
      if (candidateRequestId === requestId) {
        candidatesLoading = false;
      }
    }
  }

  async function loadBrokerAccount() {
    brokerLoading = true;
    brokerError = '';
    brokerOrderError = '';

    try {
      const status = await fetchKisBrokerAccountStatus();
      brokerStatus = status;
      if (status.ready) {
        brokerBalance = await fetchKisBrokerBalance();
        await wait(900);
        try {
          brokerOrders = await fetchKisOrderExecutions();
        } catch (err) {
          brokerOrders = null;
          brokerOrderError = err instanceof Error ? err.message : 'KIS 주문체결 내역을 불러오지 못했습니다.';
        }
      } else {
        brokerBalance = null;
        brokerOrders = null;
      }
    } catch (err) {
      brokerError = err instanceof Error ? err.message : 'KIS 계좌 정보를 불러오지 못했습니다.';
      brokerBalance = null;
      brokerOrders = null;
    } finally {
      brokerLoading = false;
    }
  }

  function wait(ms: number) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  async function checkBuyableCash() {
    const normalizedSymbol = buyableSymbol.trim();
    if (!normalizedSymbol) {
      buyableError = '종목코드를 입력해 주세요.';
      return;
    }

    buyableLoading = true;
    buyableError = '';
    buyableResult = null;

    try {
      buyableResult = await fetchKisBuyableCash({
        symbol: normalizedSymbol,
        order_type: buyableOrderType,
        order_price: buyableOrderType === 'limit' ? buyablePrice : 0
      });
    } catch (err) {
      buyableError = err instanceof Error ? err.message : 'KIS 매수가능금액을 불러오지 못했습니다.';
    } finally {
      buyableLoading = false;
    }
  }

  async function createOrderProposal() {
    if (!selectedOption) {
      proposalError = '전략을 먼저 선택해 주세요.';
      return;
    }

    proposalLoading = true;
    proposalError = '';
    orderProposal = null;
    selectedProposalSymbols = [];
    batchConfirmPhrase = '';
    batchSubmitError = '';
    batchSubmitResult = null;

    try {
      orderProposal = await createKisOrderProposal({
        strategy_code: selectedOption.code,
        max_positions: Math.max(1, Math.min(30, Number(proposalMaxPositions) || 10)),
        amount_per_symbol: Math.max(1000, Number(proposalAmountPerSymbol) || 5000000),
        order_type: proposalOrderType,
        cash_buffer_rate: Math.max(0, Math.min(50, Number(proposalCashBufferRate) || 0))
      });
      selectedProposalSymbols = orderProposal.lines
        .filter((line) => line.status === '주문 가능')
        .map((line) => line.symbol);
    } catch (err) {
      proposalError = err instanceof Error ? err.message : 'KIS 주문 제안을 생성하지 못했습니다.';
    } finally {
      proposalLoading = false;
    }
  }

  function toggleProposalLine(symbol: string, checked: boolean) {
    if (checked) {
      selectedProposalSymbols = Array.from(new Set([...selectedProposalSymbols, symbol]));
      return;
    }
    selectedProposalSymbols = selectedProposalSymbols.filter((item) => item !== symbol);
  }

  function handleProposalSelectionChange(symbol: string, event: Event) {
    toggleProposalLine(symbol, (event.currentTarget as HTMLInputElement).checked);
  }

  async function submitBatchOrders() {
    if (!orderProposal || !canSubmitBatchOrders) return;

    batchSubmitting = true;
    batchSubmitError = '';
    batchSubmitResult = null;

    try {
      batchSubmitResult = await submitKisPaperBatchOrders({
        confirm_submit: true,
        confirm_phrase: batchConfirmPhrase,
        orders: selectedProposalLines.map((line) => ({
          side: 'buy',
          symbol: line.symbol,
          name: line.name,
          quantity: line.quantity,
          order_type: line.order_type,
          price: line.order_type === 'limit' ? line.reference_price : 0,
          exchange_id: 'KRX'
        }))
      });
      await loadBrokerAccount();
    } catch (err) {
      batchSubmitError = err instanceof Error ? err.message : 'KIS 모의 일괄 주문을 제출하지 못했습니다.';
    } finally {
      batchSubmitting = false;
    }
  }

  function toStrategyCandidate(candidate: StrategyCandidateResult): StrategyCandidate {
    return {
      symbol: candidate.symbol,
      name: candidate.name,
      exchange: candidate.exchange,
      sector: candidate.sector,
      industry: candidate.industry,
      marketCap: candidate.market_cap,
      price: candidate.price,
      changePct: candidate.change_pct,
      per: candidate.per,
      pbr: candidate.pbr,
      roe: candidate.roe,
      revenueGrowth: candidate.revenue_growth,
      foreignNetBuy5d: candidate.foreign_net_buy_5d,
      institutionNetBuy5d: candidate.institution_net_buy_5d,
      supplyScore: candidate.supply_score,
      shortSaleRatio: candidate.short_sale_ratio,
      momentum: candidate.momentum,
      strategyScore: candidate.strategy_score,
      rationale: candidate.rationale,
      riskFlags: candidate.risk_flags
    };
  }

  function buildLocalCandidateRows(option: StrategyOption | null): StrategyCandidate[] {
    if (!option) return [];

    return candidateUniverse
      .map((item) => ({
        ...item,
        strategyScore: calculateStrategyScore(option.code, item),
        rationale: buildLocalRationale(option.code, item),
        riskFlags: buildLocalRiskFlags(item)
      }))
      .sort((left, right) => right.strategyScore - left.strategyScore)
      .slice(0, 12);
  }

  function calculateStrategyScore(strategyCode: string, item: CandidateUniverseRow) {
    if (strategyCode === 'relative-momentum-swing') {
      return clampScore(
        item.momentum * 0.5 +
          item.supplyScore * 0.18 +
          Math.max(item.changePct, 0) * 4 +
          item.revenueGrowth * 0.7 -
          item.shortSaleRatio * 0.8
      );
    }

    if (strategyCode === 'value-quality-factor') {
      return clampScore(
        item.roe * 2.4 +
          (30 - Math.min(item.per, 30)) * 1.35 +
          (4 - Math.min(item.pbr, 4)) * 7 +
          Math.max(item.revenueGrowth, 0) * 0.7
      );
    }

    if (strategyCode === 'growth-breakout-leader') {
      return clampScore(
        item.revenueGrowth * 1.5 +
          item.momentum * 0.35 +
          Math.max(item.changePct, 0) * 5 +
          item.supplyScore * 0.2 -
          Math.max(item.per - 35, 0) * 0.5
      );
    }

    if (strategyCode === 'trend-breakout') {
      return clampScore(
        item.momentum * 0.48 +
          Math.max(item.changePct, 0) * 6 +
          item.supplyScore * 0.25 -
          Math.max(item.shortSaleRatio - 5, 0) * 1.2
      );
    }

    if (strategyCode === 'supply-demand-accumulation') {
      return clampScore(
        item.supplyScore * 0.55 +
          Math.max(item.foreignNetBuy5d, 0) / 70 +
          Math.max(item.institutionNetBuy5d, 0) / 80 +
          item.momentum * 0.15
      );
    }

    if (strategyCode === 'low-volatility-defensive') {
      return clampScore(
        38 -
          Math.abs(item.changePct) * 4 -
          item.shortSaleRatio * 2 +
          item.roe * 2 +
          (22 - Math.min(item.per, 22)) * 0.9 +
          (3 - Math.min(item.pbr, 3)) * 6 +
          item.supplyScore * 0.12
      );
    }

    return clampScore(item.momentum * 0.35 + item.supplyScore * 0.35 + item.roe * 1.2 + Math.max(item.revenueGrowth, 0) * 0.8);
  }

  function clampScore(score: number) {
    return Math.max(0, Math.min(100, Math.round(score)));
  }

  function buildLocalRationale(strategyCode: string, item: CandidateUniverseRow) {
    if (strategyCode.startsWith('user-')) {
      return [`검색식 기반 후보`, `모멘텀 ${item.momentum}점`, `수급 점수 ${item.supplyScore}점`];
    }

    return [`모멘텀 ${item.momentum}점`, `수급 점수 ${item.supplyScore}점`, `ROE ${item.roe}%`];
  }

  function buildLocalRiskFlags(item: CandidateUniverseRow) {
    const flags: string[] = [];

    if (item.shortSaleRatio >= 6) flags.push('공매도 비율 높음');
    if (item.per >= 35) flags.push('고PER 구간');
    if (item.changePct >= 4) flags.push('단기 급등');
    if (item.roe < 6) flags.push('수익성 낮음');

    return flags;
  }

  function candidateSourceLabel(source: string) {
    if (source.startsWith('daily-price-candidates:')) {
      const provider = source.replace('daily-price-candidates:', '').replace(':filtered', '');
      const suffix = source.includes(':filtered') ? ' · 저장 조건 적용' : '';
      return `실제 일봉 기반 · ${provider}${suffix}`;
    }
    if (source.includes('filtered')) return '사용자 저장 조건 적용';
    if (source.includes('user-strategy')) return '사용자 저장 전략 · 샘플 후보군';
    if (source.includes('sample')) return '샘플 후보군';
    return source || '출처 확인 중';
  }

  function formatKrw(value: number) {
    return new Intl.NumberFormat('ko-KR', {
      style: 'currency',
      currency: 'KRW',
      maximumFractionDigits: 0
    }).format(value);
  }

  function formatNumber(value: number) {
    return value.toLocaleString('ko-KR');
  }

  function formatPercent(value: number) {
    return `${value > 0 ? '+' : ''}${value.toLocaleString('ko-KR', { maximumFractionDigits: 2 })}%`;
  }

  function formatSigned(value: number) {
    return `${value > 0 ? '+' : ''}${value.toLocaleString('ko-KR')}`;
  }

  function orderTypeLabel(value: 'market' | 'limit') {
    return value === 'market' ? '시장가' : '지정가';
  }
</script>

<svelte:head>
  <title>전략 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">전략</p>
    <h1>전략을 선택하고 해당 조건에 맞는 후보 종목을 확인합니다.</h1>
  </div>
</header>

{#if error && !dashboard}
  <section class="state-panel error">{error}</section>
{:else}
  <div class="backtest-stack">
    <section class="panel backtest-panel">
      <div class="panel-heading">
        <span>전략 선택</span>
        <strong>{loading && !selectedOption ? '전략 목록 로딩 중' : selectedOption?.name ?? '전략 선택 필요'}</strong>
      </div>
      <div class="backtest-form-grid strategy-select-grid">
        <label>
          <span>전략</span>
          <select bind:value={selectedStrategy} disabled={loading || !strategyOptions.length} onchange={handleStrategyChange}>
            {#if loading && !strategyOptions.length}
              <option value={selectedStrategy}>전략 목록을 불러오는 중입니다</option>
            {:else}
              <optgroup label={`시스템 제공 전략 (${systemStrategyOptions.length})`}>
                {#each systemStrategyOptions as item}
                  <option value={item.code}>[시스템] {strategyLabel(item)}</option>
                {/each}
              </optgroup>
              <optgroup label={`사용자 등록 전략 (${customStrategyOptions.length})`}>
                {#if customStrategyOptions.length}
                  {#each customStrategyOptions as item}
                    <option value={item.code}>[사용자] {strategyLabel(item)}</option>
                  {/each}
                {:else}
                  <option disabled value="">검색기에서 전략을 등록하면 여기에 표시됩니다</option>
                {/if}
              </optgroup>
            {/if}
          </select>
        </label>
      </div>
      {#if selectedOption}
        <div class="strategy-note">
          <div class="strategy-note-title">
            <strong>{selectedOption.style}</strong>
            <span class:custom={selectedOption.sourceKind === 'custom'} class="source-badge">
              {sourceBadgeLabel(selectedOption)}
            </span>
          </div>
          <span>{selectedOption.summary}</span>
          <div class="strategy-meta-grid">
            <div>
              <span>분류</span>
              <strong>{selectedOption.category}</strong>
            </div>
            <div>
              <span>보유 기간</span>
              <strong>{selectedOption.holdingPeriod}</strong>
            </div>
            <div>
              <span>리밸런싱</span>
              <strong>{selectedOption.rebalanceRule}</strong>
            </div>
          </div>
          <div class="strategy-rule-grid">
            <div>
              <strong>후보 조건</strong>
              <ul class="compact-list">
                {#each firstRules(selectedOption.signalRules) as rule}
                  <li>
                    <span class="tooltip-anchor rule-tooltip" title={describeStrategyRule(rule, 'signal')}>
                      {rule}
                      <span class="tooltip">{describeStrategyRule(rule, 'signal')}</span>
                    </span>
                  </li>
                {/each}
              </ul>
            </div>
            <div>
              <strong>우선순위</strong>
              <ul class="compact-list">
                {#each firstRules(selectedOption.rankingRules) as rule}
                  <li>
                    <span class="tooltip-anchor rule-tooltip" title={describeStrategyRule(rule, 'ranking')}>
                      {rule}
                      <span class="tooltip">{describeStrategyRule(rule, 'ranking')}</span>
                    </span>
                  </li>
                {/each}
              </ul>
            </div>
            <div>
              <strong>위험 제어</strong>
              <ul class="compact-list">
                {#each firstRules(selectedOption.riskControls) as rule}
                  <li>
                    <span class="tooltip-anchor rule-tooltip" title={describeStrategyRule(rule, 'risk')}>
                      {rule}
                      <span class="tooltip">{describeStrategyRule(rule, 'risk')}</span>
                    </span>
                  </li>
                {/each}
              </ul>
            </div>
          </div>
          <div class="tag-row">
            <span>{selectedOption.source}</span>
            {#each selectedOption.dataRequirements ?? [] as requirement}
              <span>{requirement}</span>
            {/each}
          </div>
          <div class="action-row">
            <a class="button secondary" href={backtestHref(selectedOption)}>이 전략 백테스트</a>
          </div>
          {#if selectedOption.formula}
            <code class="formula-box compact-formula">{selectedOption.formula}</code>
          {/if}
        </div>
      {:else}
        <div class="empty-state">전략 목록을 불러오는 중입니다.</div>
      {/if}
    </section>

    <section class="panel broker-panel">
      <div class="panel-heading inline">
        <div>
          <span>KIS 모의 계좌</span>
          <strong>{brokerStatus?.account_label || '계좌 확인 중'}</strong>
        </div>
        <button type="button" class="secondary" onclick={loadBrokerAccount} disabled={brokerLoading}>
          {brokerLoading ? '갱신 중' : '새로고침'}
        </button>
      </div>
      {#if brokerError}
        <div class="empty-state error">{brokerError}</div>
      {:else if brokerLoading && !brokerStatus}
        <div class="empty-state">KIS 계좌 상태를 확인하는 중입니다.</div>
      {:else if brokerStatus && !brokerStatus.ready}
        <div class="broker-status-row">
          <span class="source-badge custom">설정 필요</span>
          <strong>{brokerStatus.message}</strong>
        </div>
      {:else if brokerStatus}
        <div class="broker-status-row">
          <span class="source-badge">{brokerStatus.environment === 'paper' ? '모의투자' : '실전 읽기'}</span>
          <strong>{brokerStatus.message}</strong>
          <span>{brokerStatus.paper_trading_enabled ? '모의주문 허용' : '모의주문 잠김'}</span>
        </div>
        {#if brokerBalance}
          <div class="broker-summary-grid">
            <div>
              <span>순자산</span>
              <strong>{formatKrw(brokerBalance.summary.net_asset_amount)}</strong>
            </div>
            <div>
              <span>총평가금액</span>
              <strong>{formatKrw(brokerBalance.summary.total_evaluation_amount)}</strong>
            </div>
            <div>
              <span>평가손익</span>
              <strong
                class:tone-positive={brokerBalance.summary.profit_loss_amount > 0}
                class:tone-caution={brokerBalance.summary.profit_loss_amount < 0}
              >
                {formatKrw(brokerBalance.summary.profit_loss_amount)}
              </strong>
            </div>
            <div>
              <span>평가손익률</span>
              <strong
                class:tone-positive={brokerBalance.summary.profit_loss_rate > 0}
                class:tone-caution={brokerBalance.summary.profit_loss_rate < 0}
              >
                {formatPercent(brokerBalance.summary.profit_loss_rate)}
              </strong>
            </div>
            <div>
              <span>예수금</span>
              <strong>{formatKrw(brokerBalance.summary.deposit_amount)}</strong>
            </div>
            <div>
              <span>보유 종목</span>
              <strong>{formatNumber(brokerBalance.holdings.length)}개</strong>
            </div>
          </div>
          <div class="buyable-panel">
            <div class="broker-subsection-heading">
              <div>
                <span>매수가능 조회</span>
                <strong>종목별 주문 전 현금 확인</strong>
              </div>
            </div>
            <div class="buyable-form">
              <label>
                <span>종목코드</span>
                <input bind:value={buyableSymbol} placeholder="005930" />
              </label>
              <label>
                <span>주문방식</span>
                <select bind:value={buyableOrderType}>
                  <option value="market">시장가</option>
                  <option value="limit">지정가</option>
                </select>
              </label>
              <label>
                <span>지정가</span>
                <input
                  bind:value={buyablePrice}
                  disabled={buyableOrderType === 'market'}
                  min="0"
                  type="number"
                />
              </label>
              <button type="button" class="secondary" onclick={checkBuyableCash} disabled={buyableLoading}>
                {buyableLoading ? '조회 중' : '조회'}
              </button>
            </div>
            {#if buyableError}
              <div class="empty-state error">{buyableError}</div>
            {:else if buyableResult}
              <div class="broker-summary-grid compact-summary-grid">
                <div>
                  <span>미수 없는 매수금액</span>
                  <strong>{formatKrw(buyableResult.cash_buy_amount)}</strong>
                </div>
                <div>
                  <span>미수 없는 매수수량</span>
                  <strong>{formatNumber(buyableResult.cash_buy_quantity)}주</strong>
                </div>
                <div>
                  <span>최대 매수금액</span>
                  <strong>{formatKrw(buyableResult.max_buy_amount)}</strong>
                </div>
                <div>
                  <span>최대 매수수량</span>
                  <strong>{formatNumber(buyableResult.max_buy_quantity)}주</strong>
                </div>
              </div>
            {/if}
          </div>
          {#if brokerBalance.holdings.length}
            <div class="table-wrap compact-table-wrap">
              <table class="wide-table broker-holdings-table">
                <thead>
                  <tr>
                    <th>종목</th>
                    <th>보유</th>
                    <th>주문가능</th>
                    <th>평균단가</th>
                    <th>현재가</th>
                    <th>평가금액</th>
                    <th>평가손익</th>
                  </tr>
                </thead>
                <tbody>
                  {#each brokerBalance.holdings.slice(0, 8) as holding}
                    <tr>
                      <td>
                        <strong>{holding.name || holding.symbol}</strong>
                        <span>{holding.symbol}</span>
                      </td>
                      <td>{formatNumber(holding.holding_quantity)}주</td>
                      <td>{formatNumber(holding.orderable_quantity)}주</td>
                      <td>{formatKrw(holding.average_price)}</td>
                      <td>{formatKrw(holding.current_price)}</td>
                      <td>{formatKrw(holding.evaluation_amount)}</td>
                      <td
                        class:tone-positive={holding.profit_loss_amount > 0}
                        class:tone-caution={holding.profit_loss_amount < 0}
                      >
                        <strong>{formatKrw(holding.profit_loss_amount)}</strong>
                        <span>{formatPercent(holding.profit_loss_rate)}</span>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {:else}
            <div class="empty-state">현재 조회된 보유 종목이 없습니다.</div>
          {/if}
          {#if brokerOrderError}
            <div class="broker-subsection-heading">
              <div>
                <span>최근 주문체결</span>
                <strong>조회 보류</strong>
              </div>
            </div>
            <div class="empty-state error">{brokerOrderError}</div>
          {:else if brokerOrders}
            <div class="broker-subsection-heading">
              <div>
                <span>최근 주문체결</span>
                <strong>{brokerOrders.start_date} ~ {brokerOrders.end_date}</strong>
              </div>
              <span>
                주문 {formatNumber(brokerOrders.summary.total_order_quantity)}주 · 체결
                {formatNumber(brokerOrders.summary.total_filled_quantity)}주
              </span>
            </div>
            {#if brokerOrders.orders.length}
              <div class="table-wrap compact-table-wrap">
                <table class="wide-table broker-holdings-table">
                  <thead>
                    <tr>
                      <th>일시</th>
                      <th>종목</th>
                      <th>구분</th>
                      <th>상태</th>
                      <th>주문수량</th>
                      <th>체결수량</th>
                      <th>잔여</th>
                      <th>주문가</th>
                      <th>평균가</th>
                      <th>주문번호</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each brokerOrders.orders.slice(0, 10) as order}
                      <tr>
                        <td>
                          <strong>{order.order_date}</strong>
                          <span>{order.order_time}</span>
                        </td>
                        <td>
                          <strong>{order.name || order.symbol}</strong>
                          <span>{order.symbol}</span>
                        </td>
                        <td>{order.side_name || order.side_code}</td>
                        <td>{order.status}</td>
                        <td>{formatNumber(order.ordered_quantity)}주</td>
                        <td>{formatNumber(order.filled_quantity)}주</td>
                        <td>{formatNumber(order.remaining_quantity)}주</td>
                        <td>{formatKrw(order.order_price)}</td>
                        <td>{formatKrw(order.average_price)}</td>
                        <td>{order.order_no}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {:else}
              <div class="empty-state">최근 14일 주문체결 내역이 없습니다.</div>
            {/if}
          {/if}
        {/if}
      {/if}
    </section>

    <section class="panel order-proposal-panel">
      <div class="panel-heading inline">
        <div>
          <span>전략 주문 제안</span>
          <strong>{selectedOption?.name ?? '전략 선택 필요'}</strong>
        </div>
        {#if orderProposal}
          <span class="muted">{orderProposal.generated_at.replace('T', ' ')} · {orderProposal.proposal_id}</span>
        {/if}
      </div>
      <div class="order-proposal-form">
        <label>
          <span>종목 수</span>
          <input bind:value={proposalMaxPositions} min="1" max="30" type="number" />
        </label>
        <label>
          <span>종목당 금액</span>
          <input bind:value={proposalAmountPerSymbol} min="100000" step="100000" type="number" />
        </label>
        <label>
          <span>주문 방식</span>
          <select bind:value={proposalOrderType}>
            <option value="market">시장가</option>
            <option value="limit">지정가 기준</option>
          </select>
        </label>
        <label>
          <span>현금 버퍼</span>
          <input bind:value={proposalCashBufferRate} min="0" max="50" step="1" type="number" />
        </label>
        <button type="button" onclick={createOrderProposal} disabled={proposalLoading || !selectedOption}>
          {proposalLoading ? '계산 중' : '제안 생성'}
        </button>
      </div>
      {#if proposalError}
        <div class="empty-state error">{proposalError}</div>
      {:else if proposalLoading}
        <div class="empty-state">전략 후보를 주문 제안으로 계산하는 중입니다.</div>
      {:else if orderProposal}
        <div class="broker-summary-grid compact-summary-grid">
          <div>
            <span>주문 가능 후보</span>
            <strong>{formatNumber(orderProposal.executable_count)}개</strong>
          </div>
          <div>
            <span>예상 주문금액</span>
            <strong>{formatKrw(orderProposal.total_estimated_amount)}</strong>
          </div>
          <div>
            <span>예수금</span>
            <strong>{formatKrw(orderProposal.available_cash)}</strong>
          </div>
          <div>
            <span>현금 버퍼</span>
            <strong>{formatKrw(orderProposal.cash_buffer_amount)}</strong>
          </div>
          <div>
            <span>주문 방식</span>
            <strong>{orderTypeLabel(orderProposal.order_type)}</strong>
          </div>
          <div>
            <span>후보 출처</span>
            <strong>{candidateSourceLabel(orderProposal.source)}</strong>
          </div>
        </div>
        {#if orderProposal.warnings.length}
          <div class="proposal-warnings">
            {#each orderProposal.warnings as warning}
              <span>{warning}</span>
            {/each}
          </div>
        {/if}
        <div class="batch-order-controls">
          <div>
            <span>선택 주문</span>
            <strong>{formatNumber(selectedProposalLines.length)}개 · {formatKrw(selectedProposalAmount)}</strong>
          </div>
          <label>
            <span>확인 문구</span>
            <input
              bind:value={batchConfirmPhrase}
              disabled={!brokerStatus?.paper_trading_enabled || batchSubmitting}
              placeholder="모의주문 실행"
            />
          </label>
          <button type="button" onclick={submitBatchOrders} disabled={!canSubmitBatchOrders}>
            {batchSubmitting ? '제출 중' : '모의 일괄 주문'}
          </button>
        </div>
        {#if batchSubmitError}
          <div class="empty-state error">{batchSubmitError}</div>
        {:else if batchSubmitResult}
          <div class="broker-summary-grid compact-summary-grid">
            <div>
              <span>일괄 주문 상태</span>
              <strong>{batchSubmitResult.status === 'success' ? '제출 완료' : '부분 실패'}</strong>
            </div>
            <div>
              <span>제출 성공</span>
              <strong>{formatNumber(batchSubmitResult.submitted_count)}건</strong>
            </div>
            <div>
              <span>제출 실패</span>
              <strong>{formatNumber(batchSubmitResult.failed_count)}건</strong>
            </div>
            <div>
              <span>예상 주문금액</span>
              <strong>{formatKrw(batchSubmitResult.total_estimated_amount)}</strong>
            </div>
          </div>
        {/if}
        <div class="table-wrap compact-table-wrap">
          <table class="wide-table broker-holdings-table">
            <thead>
              <tr>
                <th>선택</th>
                <th>종목</th>
                <th>점수</th>
                <th>방식</th>
                <th>기준가</th>
                <th>수량</th>
                <th>예상금액</th>
                <th>상태</th>
                <th>선정 사유</th>
              </tr>
            </thead>
            <tbody>
              {#each orderProposal.lines as line}
                <tr>
                  <td>
                    <input
                      checked={selectedProposalSymbols.includes(line.symbol)}
                      disabled={line.status !== '주문 가능' || batchSubmitting}
                      type="checkbox"
                      onchange={(event) => handleProposalSelectionChange(line.symbol, event)}
                    />
                  </td>
                  <td>
                    <strong>{line.name || line.symbol}</strong>
                    <span>{line.symbol}</span>
                  </td>
                  <td class="rank-cell">{line.strategy_score}</td>
                  <td>{orderTypeLabel(line.order_type)}</td>
                  <td>{formatKrw(line.reference_price)}</td>
                  <td>{formatNumber(line.quantity)}주</td>
                  <td>{formatKrw(line.estimated_amount)}</td>
                  <td
                    class:tone-positive={line.status === '주문 가능'}
                    class:tone-caution={line.status !== '주문 가능'}
                  >
                    <strong>{line.status}</strong>
                    {#if line.warnings.length}
                      <span>{line.warnings.join(' / ')}</span>
                    {/if}
                  </td>
                  <td>
                    <ul class="compact-list">
                      {#each line.rationale as reason}
                        <li>{reason}</li>
                      {/each}
                    </ul>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>

    <section class="panel screener-results">
      <div class="panel-heading inline">
        <div>
          <span>전략 검색 결과</span>
          <strong>{loading && !selectedOption ? '대기 중' : `${candidateRows.length}개 종목`}</strong>
        </div>
        <span class="muted">
          {loading && !selectedOption
            ? '전략 목록 로딩 중'
            : candidatesLoading
            ? '후보 계산 중'
            : `${candidateSourceLabel(candidateSource)} · 전략 점수 평균 ${averageScore || '-'}`}
        </span>
      </div>
      {#if candidatesError}
        <div class="empty-state">{candidatesError}</div>
      {:else if loading && !selectedOption}
        <div class="empty-state">전략 목록이 준비되면 후보 종목을 계산합니다.</div>
      {:else if candidatesLoading}
        <div class="empty-state">전략 후보 종목을 계산하는 중입니다.</div>
      {:else}
        <div class="table-wrap">
        <table class="wide-table strategy-result-table">
          <thead>
            <tr>
              {#each candidateColumns as column}
                <th>
                  <button class="tooltip-anchor column-tooltip" title={column.description} type="button">
                    {column.label}
                    <span class="tooltip">{column.description}</span>
                  </button>
                </th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each candidateRows as row}
              <tr>
                <td>
                  <strong>{row.name}</strong>
                  <span>{row.symbol} · {row.industry}</span>
                </td>
                <td class="rank-cell">{row.strategyScore}</td>
                <td>
                  <ul class="compact-list">
                    {#each row.rationale as reason}
                      <li>{reason}</li>
                    {/each}
                  </ul>
                  {#if row.riskFlags.length}
                    <div class="tag-row compact-tags">
                      {#each row.riskFlags as flag}
                        <span>{flag}</span>
                      {/each}
                    </div>
                  {/if}
                </td>
                <td>{row.exchange}</td>
                <td>{row.sector}</td>
                <td>{row.marketCap.toLocaleString('ko-KR')}조</td>
                <td>{formatKrw(row.price)}</td>
                <td class:tone-positive={row.changePct > 0} class:tone-caution={row.changePct < 0}>
                  <strong>{row.changePct}%</strong>
                </td>
                <td>{row.per}x</td>
                <td>{row.pbr}x</td>
                <td>{row.roe}%</td>
                <td>{row.revenueGrowth}%</td>
                <td class:tone-positive={row.foreignNetBuy5d > 0} class:tone-caution={row.foreignNetBuy5d < 0}>
                  <strong>{formatSigned(row.foreignNetBuy5d)}억</strong>
                </td>
                <td class:tone-positive={row.institutionNetBuy5d > 0} class:tone-caution={row.institutionNetBuy5d < 0}>
                  <strong>{formatSigned(row.institutionNetBuy5d)}억</strong>
                </td>
                <td>{row.supplyScore}</td>
                <td>{row.shortSaleRatio}%</td>
                <td>
                  <meter min="0" max="100" value={row.momentum}>{row.momentum}</meter>
                  <b>{row.momentum}</b>
                </td>
              </tr>
            {:else}
              <tr>
                <td colspan="17">
                  <div class="empty-state">현재 선택한 전략에 맞는 종목이 없습니다.</div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
        </div>
      {/if}
    </section>
  </div>
{/if}
