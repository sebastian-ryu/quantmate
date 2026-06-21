<script lang="ts">
  import { onMount, tick } from 'svelte';
  import {
    fetchDashboard,
    fetchStrategyCandidates,
    type Dashboard,
    type Strategy,
    type StrategyCandidateResult,
    fetchUserStrategies,
    type UserStrategy
  } from '$lib/api';

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
  let loading = true;
  let error = '';

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
      await tick();
      await loadCandidateRowsForSelectedStrategy();
    } catch (err) {
      error = err instanceof Error ? err.message : '전략 데이터를 불러오지 못했습니다.';
    } finally {
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

  function formatSigned(value: number) {
    return `${value > 0 ? '+' : ''}${value.toLocaleString('ko-KR')}`;
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

{#if loading}
  <section class="state-panel">전략 데이터를 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else if dashboard}
  <div class="backtest-stack">
    <section class="panel backtest-panel">
      <div class="panel-heading">
        <span>전략 선택</span>
        <strong>{selectedOption?.name ?? '전략 선택 필요'}</strong>
      </div>
      <div class="backtest-form-grid strategy-select-grid">
        <label>
          <span>전략</span>
          <select bind:value={selectedStrategy} onchange={handleStrategyChange}>
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
                  <li>{rule}</li>
                {/each}
              </ul>
            </div>
            <div>
              <strong>우선순위</strong>
              <ul class="compact-list">
                {#each firstRules(selectedOption.rankingRules) as rule}
                  <li>{rule}</li>
                {/each}
              </ul>
            </div>
            <div>
              <strong>위험 제어</strong>
              <ul class="compact-list">
                {#each firstRules(selectedOption.riskControls) as rule}
                  <li>{rule}</li>
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
      {/if}
    </section>

    <section class="panel screener-results">
      <div class="panel-heading inline">
        <div>
          <span>전략 검색 결과</span>
          <strong>{candidateRows.length}개 종목</strong>
        </div>
        <span class="muted">
          {candidatesLoading
            ? '후보 계산 중'
            : `${candidateSourceLabel(candidateSource)} · 전략 점수 평균 ${averageScore || '-'}`}
        </span>
      </div>
      {#if candidatesError}
        <div class="empty-state">{candidatesError}</div>
      {:else if candidatesLoading}
        <div class="empty-state">전략 후보 종목을 계산하는 중입니다.</div>
      {:else}
        <div class="table-wrap">
        <table class="wide-table strategy-result-table">
          <thead>
            <tr>
              <th>종목</th>
              <th>전략 점수</th>
              <th>선정 사유</th>
              <th>거래소</th>
              <th>섹터</th>
              <th>시가총액</th>
              <th>가격</th>
              <th>등락</th>
              <th>PER</th>
              <th>PBR</th>
              <th>ROE</th>
              <th>성장</th>
              <th>외국인 5일</th>
              <th>기관 5일</th>
              <th>수급 점수</th>
              <th>공매도</th>
              <th>모멘텀</th>
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
