<script lang="ts">
  import { onMount, tick } from 'svelte';
  import DataRefreshPanel from '$lib/DataRefreshPanel.svelte';
  import {
    createKisOrderProposal,
    fetchDashboard,
    fetchKisBuyableCash,
    fetchKisBrokerAccountStatus,
    fetchKisBrokerBalance,
    fetchKisTradingSafetyStatus,
    fetchKisOrderExecutions,
    fetchKisRealtimeLatestQuotes,
    fetchKisRealtimeQuoteStatus,
    fetchStrategyCandidates,
    fetchStrategyExecutionContract,
    fetchStrategyPerformance,
    type Dashboard,
    type DataFreshness,
    type KisBuyableCash,
    type KisBrokerAccountStatus,
    type KisBrokerBalance,
    type KisOrderProposal,
    type KisPaperBatchOrderResponse,
    type KisOrderExecutions,
    type KisRealtimeQuote,
    type KisRealtimeQuoteStatus,
    type KisTradingSafetyStatus,
    type Strategy,
    type StrategyCandidateResult,
    type StrategyExecutionContract,
    type StrategyPerformanceSnapshot,
    stopKisRealtimeQuotes,
    submitKisPaperBatchOrders,
    subscribeKisRealtimeQuotes,
    fetchUserStrategies,
    type UserStrategy
  } from '$lib/api';
  import {
    classifyRiskRule,
    describeStrategyRule,
    riskRuleActionDescription,
    riskRuleActionLabel
  } from '$lib/strategyRuleTooltips';

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
    performance: StrategyPerformanceSnapshot | null;
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

  let dashboard: Dashboard | null = null;
  let selectedStrategy = 'relative-momentum-swing';
  let registeredStrategies: UserStrategy[] = [];
  let strategyPerformanceByCode: Record<string, StrategyPerformanceSnapshot> = {};
  let candidateRows: StrategyCandidate[] = [];
  let candidateSource = '';
  let candidateFreshness: DataFreshness | null = null;
  let candidatesLoading = false;
  let candidatesError = '';
  let candidateRequestId = 0;
  let executionContract: StrategyExecutionContract | null = null;
  let executionContractLoading = false;
  let executionContractError = '';
  let executionContractRequestId = 0;
  let brokerStatus: KisBrokerAccountStatus | null = null;
  let tradingSafety: KisTradingSafetyStatus | null = null;
  let brokerBalance: KisBrokerBalance | null = null;
  let brokerOrders: KisOrderExecutions | null = null;
  let brokerLoading = false;
  let brokerError = '';
  let tradingSafetyError = '';
  let brokerOrderError = '';
  let realtimeStatus: KisRealtimeQuoteStatus | null = null;
  let realtimeQuotes: KisRealtimeQuote[] = [];
  let realtimeLoading = false;
  let realtimeError = '';
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
      void loadExecutionContract(selectedStrategy);
      void loadCandidateRowsForSelectedStrategy();
      void loadBrokerStatus();
      void loadRealtimeStatus();
      void loadStrategyPerformance();
    } catch (err) {
      error = err instanceof Error ? err.message : '전략 데이터를 불러오지 못했습니다.';
      loading = false;
    }
  });

  onMount(() => {
    const timer = window.setInterval(() => {
      if (realtimeStatus?.running) {
        void loadRealtimeLatestQuotesOnly();
      }
    }, 5000);

    return () => window.clearInterval(timer);
  });

  $: baseStrategies = dashboard?.strategies ?? [];
  $: strategyOptions = [
    ...baseStrategies.map((strategy) => toBaseStrategyOption(strategy, strategyPerformanceByCode)),
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
  $: brokerEnvironmentTitle =
    brokerStatus?.environment === 'paper'
      ? 'KIS 모의 계좌'
      : brokerStatus?.environment === 'real'
        ? 'KIS 실전 계좌'
        : 'KIS 계좌';
  $: brokerEnvironmentBadge =
    brokerStatus?.environment === 'paper'
      ? '모의투자'
      : brokerStatus?.environment === 'real'
        ? '실전 읽기'
        : '환경 확인';
  $: brokerEnvironmentClass =
    brokerStatus?.environment === 'paper'
      ? 'paper'
      : brokerStatus?.environment === 'real'
        ? 'live'
        : 'custom';
  $: brokerPermissionText = brokerStatus
    ? brokerStatus.environment === 'paper'
      ? brokerStatus.paper_trading_enabled
        ? '모의주문 허용'
        : '모의주문 잠김'
      : brokerStatus.live_trading_enabled
        ? '실거래 활성화됨'
        : '실전 읽기 전용'
    : '';
  $: confirmationRequired = tradingSafety?.manual_confirmation_required ?? true;
  $: canSubmitBatchOrders =
    Boolean(tradingSafety?.can_submit_paper_orders ?? brokerStatus?.paper_trading_enabled) &&
    selectedProposalLines.length > 0 &&
    (!confirmationRequired || batchConfirmPhrase.trim() === '모의주문 실행') &&
    !batchSubmitting;
  $: tradingSafetyStatusText = tradingSafety
    ? tradingSafety.emergency_stop_enabled
      ? '긴급 중지'
      : tradingSafety.can_submit_paper_orders
        ? '모의주문 가능'
        : '주문 잠김'
    : '상태 확인 중';

  async function loadStrategyPerformance(refresh = false) {
    try {
      const rows = await fetchStrategyPerformance(refresh);
      strategyPerformanceByCode = Object.fromEntries(rows.map((row) => [row.strategy_code, row.performance]));
    } catch {
      strategyPerformanceByCode = {};
    }
  }

  function toBaseStrategyOption(
    strategy: Strategy,
    performanceByCode: Record<string, StrategyPerformanceSnapshot>
  ): StrategyOption {
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
      references: strategy.references ?? [],
      performance: performanceByCode[strategy.code] ?? strategy.performance ?? null
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
      performance: null,
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

  function describeRiskRule(rule: string) {
    return `${riskRuleActionDescription(rule)} ${describeStrategyRule(rule, 'risk')}`;
  }

  async function handleStrategyChange() {
    orderProposal = null;
    selectedProposalSymbols = [];
    batchConfirmPhrase = '';
    batchSubmitError = '';
    batchSubmitResult = null;
    proposalError = '';
    void loadExecutionContract(selectedStrategy);
    await loadCandidateRowsForSelectedStrategy();
  }

  async function loadCandidateRowsForSelectedStrategy() {
    await tick();
    await loadCandidateRows(selectedOption);
  }

  async function reloadAfterDataRefresh() {
    await loadCandidateRowsForSelectedStrategy();
    await loadStrategyPerformance(true);
  }

  async function loadExecutionContract(strategyCode: string) {
    const requestId = executionContractRequestId + 1;
    executionContractRequestId = requestId;
    executionContractError = '';

    if (!strategyCode) {
      executionContract = null;
      return;
    }

    executionContractLoading = true;

    try {
      const result = await fetchStrategyExecutionContract(strategyCode);
      if (executionContractRequestId !== requestId) return;
      executionContract = result;
    } catch (err) {
      if (executionContractRequestId !== requestId) return;
      executionContract = null;
      executionContractError = err instanceof Error ? err.message : '전략 실행 계약을 불러오지 못했습니다.';
    } finally {
      if (executionContractRequestId === requestId) {
        executionContractLoading = false;
      }
    }
  }

  async function loadCandidateRows(option: StrategyOption | null) {
    const requestId = candidateRequestId + 1;
    candidateRequestId = requestId;
    candidatesError = '';

    if (!option) {
      candidateRows = [];
      candidateSource = '';
      candidateFreshness = null;
      return;
    }

    candidatesLoading = true;

    try {
      const response = await fetchStrategyCandidates(option.code);
      if (candidateRequestId !== requestId) return;
      candidateRows = response.candidates.map(toStrategyCandidate);
      if (!buyableSymbol && candidateRows[0]?.symbol) buyableSymbol = candidateRows[0].symbol;
      candidateSource = response.source;
      candidateFreshness = response.data_freshness;
    } catch (err) {
      if (candidateRequestId !== requestId) return;
      candidatesError = err instanceof Error ? err.message : '전략 후보 종목을 불러오지 못했습니다.';
      candidateRows = [];
      candidateSource = '';
      candidateFreshness = null;
    } finally {
      if (candidateRequestId === requestId) {
        candidatesLoading = false;
      }
    }
  }

  async function loadBrokerStatus() {
    brokerLoading = true;
    brokerError = '';
    brokerOrderError = '';
    tradingSafetyError = '';

    try {
      const status = await fetchKisBrokerAccountStatus();
      brokerStatus = status;
      if (!status.ready) {
        brokerBalance = null;
        brokerOrders = null;
      }
      await loadTradingSafetyStatus();
    } catch (err) {
      brokerError = err instanceof Error ? err.message : 'KIS 계좌 정보를 불러오지 못했습니다.';
      brokerBalance = null;
      brokerOrders = null;
    } finally {
      brokerLoading = false;
    }
  }

  async function loadTradingSafetyStatus() {
    try {
      tradingSafety = await fetchKisTradingSafetyStatus();
      tradingSafetyError = '';
    } catch (err) {
      tradingSafety = null;
      tradingSafetyError = err instanceof Error ? err.message : 'KIS 주문 안전 상태를 불러오지 못했습니다.';
    }
  }

  async function loadRealtimeStatus() {
    try {
      realtimeStatus = await fetchKisRealtimeQuoteStatus();
      realtimeQuotes = await fetchKisRealtimeLatestQuotes();
      realtimeError = '';
    } catch (err) {
      realtimeError = err instanceof Error ? err.message : 'KIS 실시간 시세 상태를 불러오지 못했습니다.';
    }
  }

  async function loadRealtimeLatestQuotesOnly() {
    try {
      realtimeStatus = await fetchKisRealtimeQuoteStatus();
      realtimeQuotes = await fetchKisRealtimeLatestQuotes();
      realtimeError = '';
    } catch (err) {
      realtimeError = err instanceof Error ? err.message : 'KIS 실시간 시세를 갱신하지 못했습니다.';
    }
  }

  async function subscribeTopCandidateRealtimeQuotes() {
    const symbols = candidateRows.slice(0, 10).map((row) => row.symbol);
    if (!symbols.length) {
      realtimeError = '구독할 전략 후보 종목이 없습니다.';
      return;
    }

    realtimeLoading = true;
    realtimeError = '';

    try {
      realtimeStatus = await subscribeKisRealtimeQuotes(symbols);
      realtimeQuotes = await fetchKisRealtimeLatestQuotes();
    } catch (err) {
      realtimeError = err instanceof Error ? err.message : 'KIS 실시간 시세 구독을 시작하지 못했습니다.';
    } finally {
      realtimeLoading = false;
    }
  }

  async function stopRealtimeQuotes() {
    realtimeLoading = true;
    realtimeError = '';

    try {
      realtimeStatus = await stopKisRealtimeQuotes();
      realtimeQuotes = await fetchKisRealtimeLatestQuotes();
    } catch (err) {
      realtimeError = err instanceof Error ? err.message : 'KIS 실시간 시세 연결을 종료하지 못했습니다.';
    } finally {
      realtimeLoading = false;
    }
  }

  async function loadBrokerAccount() {
    brokerLoading = true;
    brokerError = '';
    brokerOrderError = '';
    tradingSafetyError = '';

    try {
      const status = await fetchKisBrokerAccountStatus();
      brokerStatus = status;
      await loadTradingSafetyStatus();
      if (!status.ready) {
        brokerBalance = null;
        brokerOrders = null;
        return;
      }

      brokerBalance = await fetchKisBrokerBalance();
      await wait(900);
      try {
        brokerOrders = await fetchKisOrderExecutions();
      } catch (err) {
        brokerOrders = null;
        brokerOrderError = err instanceof Error ? err.message : 'KIS 주문체결 내역을 불러오지 못했습니다.';
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
      await loadTradingSafetyStatus();
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
        confirm_phrase: confirmationRequired ? batchConfirmPhrase : '',
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

  function freshnessLabel(freshness: DataFreshness | null) {
    if (!freshness) return '기준일 확인 중';
    if (freshness.daily_price_status === 'stale') {
      return freshness.latest_daily_price_date
        ? `일봉 지연 ${freshness.latest_daily_price_date}`
        : '일봉 지연';
    }
    if (freshness.daily_price_status === 'missing') return '일봉 없음';
    return freshness.latest_daily_price_date
      ? `일봉 ${freshness.latest_daily_price_date}`
      : freshness.message;
  }

  function freshnessTooltip(freshness: DataFreshness | null) {
    if (!freshness) return '데이터 기준일을 확인하고 있습니다.';
    return [
      freshness.message,
      `기대 일봉 기준일: ${freshness.expected_daily_price_date ?? '확인 안 됨'}`,
      `일봉 상태: ${freshness.daily_price_status}`,
      `일봉 제공처: ${freshness.daily_price_providers.length ? freshness.daily_price_providers.join(', ') : '없음'}`,
      `현재가: ${freshness.latest_quote_snapshot_date ?? '없음'}`,
      `수급: ${freshness.latest_supply_flow_date ?? '없음'}`,
      `리스크: ${freshness.latest_risk_indicator_date ?? '없음'}`,
      `재무: ${freshness.latest_fundamental_period ?? '없음'}`,
      ...(freshness.warnings ?? [])
    ].join('\n');
  }

  function formatKrw(value: number) {
    return new Intl.NumberFormat('ko-KR', {
      style: 'currency',
      currency: 'KRW',
      maximumFractionDigits: 0
    }).format(value);
  }

  function formatNullableKrw(value: number | null) {
    return value === null ? '-' : formatKrw(value);
  }

  function formatNumber(value: number) {
    return value.toLocaleString('ko-KR');
  }

  function formatNullableNumber(value: number | null) {
    return value === null ? '-' : value.toLocaleString('ko-KR');
  }

  function formatPercent(value: number) {
    return `${value > 0 ? '+' : ''}${value.toLocaleString('ko-KR', { maximumFractionDigits: 2 })}%`;
  }

  function formatPerformancePercent(value: number | null) {
    if (value === null || value === undefined) return '-';
    return `${value > 0 ? '+' : ''}${value.toLocaleString('ko-KR', { maximumFractionDigits: 1 })}%`;
  }

  function performanceTooltip(performance: StrategyPerformanceSnapshot) {
    return [
      performance.note,
      `계산 기준일: ${performance.as_of}`,
      `일봉 기준일: ${performance.data_as_of ?? '확인 안 됨'}`,
      `초기금액: ${formatKrw(performance.initial_amount)}`,
      `출처: ${performance.source}`,
      performance.update_policy
    ].join('\n');
  }

  function formatDateTime(value: string) {
    return new Intl.DateTimeFormat('ko-KR', {
      year: '2-digit',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    }).format(new Date(value));
  }

  function formatSigned(value: number) {
    return `${value > 0 ? '+' : ''}${value.toLocaleString('ko-KR')}`;
  }

  function realtimeStatusLabel(status: KisRealtimeQuoteStatus | null) {
    if (!status) return '상태 확인 중';
    if (status.connected) return '수신 중';
    if (status.running) return '연결 시도 중';
    return '대기';
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
          {#if selectedOption.performance}
            <div class="strategy-performance-panel">
              <div class="performance-heading">
                <strong>최근 백테스트 수익률</strong>
                <span class="tooltip-anchor" aria-label={performanceTooltip(selectedOption.performance)}>
                  {selectedOption.performance.data_as_of ?? selectedOption.performance.as_of} 기준
                  <span class="tooltip">{performanceTooltip(selectedOption.performance)}</span>
                </span>
              </div>
              <div class="performance-grid">
                {#each selectedOption.performance.windows as perfWindow}
                  <div class:muted-card={perfWindow.status === 'unavailable'}>
                    <span>{perfWindow.label}</span>
                    <strong>{formatPerformancePercent(perfWindow.cagr)}</strong>
                    <p>
                      총 {formatPerformancePercent(perfWindow.total_return)}
                      · MDD {formatPerformancePercent(perfWindow.mdd)}
                      {#if perfWindow.status === 'partial'} · 일부 기간{/if}
                    </p>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
          <div class="execution-contract-panel">
            <div class="contract-heading">
              <strong>실행 연결</strong>
              <span>같은 전략 코드로 후보 검색, 백테스트, 주문 제안을 연결합니다.</span>
            </div>
            {#if executionContractLoading && !executionContract}
              <div class="contract-status-row">
                <span class="status-pill">계약 확인 중</span>
              </div>
            {:else if executionContractError}
              <div class="contract-status-row">
                <span class="status-pill blocked">{executionContractError}</span>
              </div>
            {:else if executionContract}
              <div class="contract-status-row">
                {#each executionContract.modes as mode}
                  <span
                    class="status-pill execution-mode-pill tooltip-anchor"
                    class:ready={mode.enabled}
                    class:blocked={!mode.enabled}
                    aria-label={mode.note}
                  >
                    {mode.label}
                    <span class="tooltip">{mode.note}</span>
                  </span>
                {/each}
              </div>
              <div class="contract-provider-row">
                <span>데이터 우선순위</span>
                <strong>{executionContract.provider_priority.join(' > ')}</strong>
              </div>
            {/if}
          </div>
          <div class="strategy-rule-grid">
            <div>
              <strong>후보 조건</strong>
              <ul class="compact-list">
                {#each firstRules(selectedOption.signalRules) as rule}
                  <li>
                    <span class="tooltip-anchor rule-tooltip" aria-label={describeStrategyRule(rule, 'signal')}>
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
                    <span class="tooltip-anchor rule-tooltip" aria-label={describeStrategyRule(rule, 'ranking')}>
                      {rule}
                      <span class="tooltip">{describeStrategyRule(rule, 'ranking')}</span>
                    </span>
                  </li>
                {/each}
              </ul>
            </div>
            <div>
              <strong>위험 처리 기준</strong>
              <p class="risk-rule-summary">제외/보류, 감점, 주의 중 어떤 방식으로 반영되는지 구분합니다.</p>
              <ul class="compact-list risk-rule-list">
                {#each firstRules(selectedOption.riskControls) as rule}
                  <li class="risk-rule-item">
                    <span class={`risk-action-badge ${classifyRiskRule(rule)}`}>{riskRuleActionLabel(rule)}</span>
                    <span class="tooltip-anchor rule-tooltip" aria-label={describeRiskRule(rule)}>
                      {rule}
                      <span class="tooltip">{describeRiskRule(rule)}</span>
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
          <span>{brokerEnvironmentTitle}</span>
          <strong>{brokerStatus?.account_label || '계좌 확인 중'}</strong>
        </div>
        <button type="button" class="secondary" onclick={loadBrokerAccount} disabled={brokerLoading}>
          {brokerLoading ? '조회 중' : '계좌 상세 조회'}
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
          <span class={`source-badge ${brokerEnvironmentClass}`}>{brokerEnvironmentBadge}</span>
          <strong>{brokerStatus.message}</strong>
          <span>{brokerPermissionText}</span>
        </div>
        {#if tradingSafetyError}
          <div class="empty-state error">{tradingSafetyError}</div>
        {:else if tradingSafety}
          <div class="trading-safety-grid">
            <div>
              <span>주문 상태</span>
              <strong
                class:tone-positive={tradingSafety.can_submit_paper_orders}
                class:tone-caution={!tradingSafety.can_submit_paper_orders}
              >
                {tradingSafetyStatusText}
              </strong>
            </div>
            <div>
              <span>1회 주문 한도</span>
              <strong>{formatKrw(tradingSafety.max_order_amount_krw)}</strong>
            </div>
            <div>
              <span>오늘 잔여 주문</span>
              <strong>
                {tradingSafety.remaining_daily_order_count === null
                  ? '무제한'
                  : `${formatNumber(tradingSafety.remaining_daily_order_count)}건`}
              </strong>
            </div>
            <div>
              <span>확인 문구</span>
              <strong>{tradingSafety.manual_confirmation_required ? '필수' : '생략'}</strong>
            </div>
            <div>
              <span>긴급 중지</span>
              <strong class:tone-caution={tradingSafety.emergency_stop_enabled}>
                {tradingSafety.emergency_stop_enabled ? '켜짐' : '꺼짐'}
              </strong>
            </div>
            <div>
              <span>손실 중지</span>
              <strong class:tone-caution={tradingSafety.daily_loss_stop_enabled}>
                {tradingSafety.daily_loss_stop_enabled ? '켜짐' : '꺼짐'}
              </strong>
            </div>
            <div>
              <span>손실 한도</span>
              <strong>{formatKrw(tradingSafety.max_daily_loss_krw)}</strong>
            </div>
          </div>
          {#if tradingSafety.warnings.length}
            <div class="proposal-warnings safety-warnings">
              {#each tradingSafety.warnings.slice(0, 4) as warning}
                <span>{warning}</span>
              {/each}
            </div>
          {/if}
        {/if}
        {#if !brokerBalance && !brokerLoading}
          <div class="empty-state compact-state">계좌 상세 정보는 필요할 때만 조회합니다.</div>
        {:else if brokerBalance}
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

    <section class="panel realtime-panel">
      <div class="panel-heading inline">
        <div>
          <span>KIS 실시간 시세</span>
          <strong>{realtimeStatusLabel(realtimeStatus)}</strong>
        </div>
        <div class="action-row">
          <button
            class="secondary"
            disabled={realtimeLoading || !candidateRows.length}
            onclick={subscribeTopCandidateRealtimeQuotes}
            type="button"
          >
            {realtimeLoading ? '처리 중' : '상위 후보 구독'}
          </button>
          <button class="secondary" disabled={realtimeLoading} onclick={loadRealtimeLatestQuotesOnly} type="button">
            새로고침
          </button>
          <button class="secondary" disabled={realtimeLoading || !realtimeStatus?.running} onclick={stopRealtimeQuotes} type="button">
            중지
          </button>
        </div>
      </div>
      <div class="broker-summary-grid compact-summary-grid">
        <div>
          <span>연결 상태</span>
          <strong>{realtimeStatusLabel(realtimeStatus)}</strong>
        </div>
        <div>
          <span>구독 종목</span>
          <strong>{formatNumber(realtimeStatus?.subscribed_symbols.length ?? 0)}개</strong>
        </div>
        <div>
          <span>수신 종목</span>
          <strong>{formatNumber(realtimeStatus?.quote_count ?? realtimeQuotes.length)}개</strong>
        </div>
        <div>
          <span>마지막 수신</span>
          <strong>{realtimeStatus?.last_message_at ? formatDateTime(realtimeStatus.last_message_at) : '-'}</strong>
        </div>
      </div>
      {#if realtimeError || realtimeStatus?.last_error}
        <div class="empty-state error">{realtimeError || realtimeStatus?.last_error}</div>
      {/if}
      {#if realtimeStatus?.subscribed_symbols.length}
        <div class="tag-row compact-tags">
          {#each realtimeStatus.subscribed_symbols as symbol}
            <span>{symbol}</span>
          {/each}
        </div>
      {/if}
      {#if realtimeQuotes.length}
        <div class="table-wrap compact-table-wrap">
          <table class="compact-table realtime-quote-table">
            <thead>
              <tr>
                <th>종목</th>
                <th>체결 시각</th>
                <th>현재가</th>
                <th>등락률</th>
                <th>체결량</th>
                <th>누적 거래량</th>
                <th>매수호가</th>
                <th>매도호가</th>
              </tr>
            </thead>
            <tbody>
              {#each realtimeQuotes as quote}
                <tr>
                  <td><strong>{quote.symbol}</strong></td>
                  <td>{quote.trade_time ? formatDateTime(quote.trade_time) : '-'}</td>
                  <td>{formatNullableKrw(quote.price)}</td>
                  <td class:tone-positive={(quote.change_rate ?? 0) > 0} class:tone-caution={(quote.change_rate ?? 0) < 0}>
                    {quote.change_rate === null ? '-' : formatPercent(quote.change_rate)}
                  </td>
                  <td>{formatNullableNumber(quote.trade_volume)}</td>
                  <td>{formatNullableNumber(quote.accumulated_volume)}</td>
                  <td>{formatNullableKrw(quote.bid_price)}</td>
                  <td>{formatNullableKrw(quote.ask_price)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <div class="empty-state compact-state">상위 후보 구독을 시작하면 최근 실시간 체결값이 여기에 표시됩니다.</div>
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
              disabled={!(tradingSafety?.can_submit_paper_orders ?? brokerStatus?.paper_trading_enabled) ||
                batchSubmitting ||
                !confirmationRequired}
              placeholder={confirmationRequired ? '모의주문 실행' : '확인 문구 생략 설정'}
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
      <DataRefreshPanel
        freshness={candidateFreshness}
        source={candidateSourceLabel(candidateSource)}
        onCompleted={reloadAfterDataRefresh}
      />
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
      {#if !candidatesLoading && candidateFreshness}
        <div class="freshness-strip">
          <span class="status-pill tooltip-anchor" aria-label={freshnessTooltip(candidateFreshness)}>
            {freshnessLabel(candidateFreshness)}
            <span class="tooltip">{freshnessTooltip(candidateFreshness)}</span>
          </span>
        </div>
      {/if}
      {#if candidatesError}
        <div class="empty-state">{candidatesError}</div>
      {:else if loading && !selectedOption}
        <div class="empty-state">전략 목록이 준비되면 후보 종목을 계산합니다.</div>
      {:else if candidatesLoading}
        <div class="empty-state">전략 후보 종목을 계산하는 중입니다.</div>
      {:else}
        <div class="table-wrap strategy-results-table-wrap">
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
