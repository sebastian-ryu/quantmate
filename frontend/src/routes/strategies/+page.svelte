<script lang="ts">
  import { onMount } from 'svelte';
  import {
    fetchDashboard,
    fetchBacktestRuns,
    fetchUserStrategies,
    runBacktest as requestBacktest,
    type BacktestRunSummary,
    type BacktestRunResult,
    type Dashboard,
    type Strategy,
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

  type AnnualReturnRow = {
    year: string;
    portfolioReturn: number;
    yieldPct: number;
    balance: number;
    income: number;
  };

  type ChartTick = {
    label: string;
    x?: number;
    y?: number;
  };

  type GrowthRow = {
    label: string;
    portfolio: number;
  };

  type ChartPoint = GrowthRow & {
    x: number;
    y: number;
  };

  type ValueScale = {
    min: number;
    max: number;
  };

  let dashboard: Dashboard | null = null;
  let selectedStrategy = 'relative-momentum-swing';
  let registeredStrategies: UserStrategy[] = [];
  let loading = true;
  let error = '';

  let startYear = '2023';
  let endYear = '2025';
  let initialAmount = 10000000;
  let hasBacktestResult = false;
  let backtestRunAt = '';
  let backtestNotice = '';
  let backtestResult: BacktestRunResult | null = null;
  let backtestRunning = false;
  let backtestError = '';
  let recentBacktests: BacktestRunSummary[] = [];
  let recentBacktestsError = '';

  const chartWidth = 760;
  const chartHeight = 360;
  const chartLeft = 72;
  const chartRight = 12;
  const chartTop = 28;
  const chartBottom = 310;
  const chartPlotWidth = chartWidth - chartLeft - chartRight;
  const chartPlotHeight = chartBottom - chartTop;

  const metricDescriptions: Record<string, string> = {
    시작금액: '백테스트 시작 시점의 투자금입니다.',
    종료금액: '백테스트 종료 시점의 평가금입니다.',
    '연평균 수익률(CAGR)': '전체 기간 수익률을 연평균 복리 수익률로 환산한 값입니다.',
    변동성: '수익률이 흔들리는 정도입니다. 높을수록 손익 변동이 큽니다.',
    '최고 연도': '백테스트 기간 중 가장 높은 연간 수익률입니다.',
    '최저 연도': '백테스트 기간 중 가장 낮은 연간 수익률입니다.',
    '최대 낙폭(MDD)': '최고점 대비 가장 크게 하락한 구간의 손실률입니다.',
    '샤프 비율': '변동성 대비 초과수익을 나타내는 위험조정 성과 지표입니다.',
    '소르티노 비율': '하락 변동성만 기준으로 본 위험조정 성과 지표입니다.',
    '월평균 회전율': '월평균 포트폴리오 교체 비율입니다.'
  };

  onMount(async () => {
    try {
      const [dashboardData, userStrategies] = await Promise.all([
        fetchDashboard(),
        fetchUserStrategies()
      ]);
      dashboard = dashboardData;
      registeredStrategies = userStrategies;
      selectedStrategy = chooseInitialStrategy(dashboardData, userStrategies);
      await loadRecentBacktests();
    } catch (err) {
      error = err instanceof Error ? err.message : '전략과 백테스트 데이터를 불러오지 못했습니다.';
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
  $: annualRows = buildAnnualRows(backtestResult);
  $: growthRows = buildGrowthRows(backtestResult);
  $: rebalanceRows = backtestResult?.rebalance_history ?? [];
  $: performanceRows = backtestResult?.metrics ?? [];
  $: initialAmountValue = Number(initialAmount) || 0;
  $: growthValues = growthRows.length ? growthRows.map((row) => row.portfolio) : [initialAmountValue];
  $: growthMin = Math.min(...growthValues, initialAmountValue);
  $: growthMax = Math.max(...growthValues, initialAmountValue);
  $: growthScale = buildValueScale(growthMin, growthMax);
  $: growthChartPoints = buildChartPoints(growthRows, growthScale.min, growthScale.max);
  $: portfolioLine = growthChartPoints.map((point) => `${point.x},${point.y}`).join(' ');
  $: growthYAxisTicks = buildYAxisTicks(growthScale.min, growthScale.max);
  $: growthXAxisTicks = buildXAxisTicks(growthRows);

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
      rankingRules: ['검색 결과 순서와 점수는 실제 데이터 연결 후 계산'],
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

  function chooseInitialStrategy(dashboardData: Dashboard, userStrategies: UserStrategy[]) {
    const requestedStrategy = getRequestedStrategyCode();
    const availableCodes = new Set([
      ...dashboardData.strategies.map((strategy) => strategy.code),
      ...userStrategies.map((strategy) => strategy.code)
    ]);

    if (requestedStrategy && availableCodes.has(requestedStrategy)) {
      return requestedStrategy;
    }

    return dashboardData.backtest.strategy_code;
  }

  function getRequestedStrategyCode() {
    if (typeof window === 'undefined') return '';

    return new URLSearchParams(window.location.search).get('strategy') ?? '';
  }

  function firstRules(rules: string[] | undefined) {
    return (rules ?? []).filter(Boolean).slice(0, 4);
  }

  async function runBacktest() {
    if (!selectedOption) {
      backtestError = '백테스트할 전략을 먼저 선택하세요.';
      return;
    }

    clearBacktestResult();

    backtestRunning = true;

    try {
      const result = await requestBacktest({
        strategy_code: selectedOption.code,
        start_year: Number(startYear),
        end_year: Number(endYear),
        initial_amount: Number(initialAmount)
      });

      backtestResult = result;
      hasBacktestResult = true;
      backtestRunAt = new Date(result.run_at).toLocaleString('ko-KR');
      backtestNotice = result.notice;
      await loadRecentBacktests();
    } catch (err) {
      backtestError = err instanceof Error ? err.message : '백테스트를 실행하지 못했습니다.';
    } finally {
      backtestRunning = false;
    }
  }

  function clearBacktestResult() {
    hasBacktestResult = false;
    backtestResult = null;
    backtestRunAt = '';
    backtestNotice = '';
    backtestError = '';
  }

  async function loadRecentBacktests() {
    try {
      recentBacktests = await fetchBacktestRuns(8);
      recentBacktestsError = '';
    } catch (err) {
      recentBacktestsError = err instanceof Error ? err.message : '최근 백테스트 결과를 불러오지 못했습니다.';
    }
  }

  function buildAnnualRows(result: BacktestRunResult | null): AnnualReturnRow[] {
    return (
      result?.annual_returns.map((row) => ({
        year: row.year,
        portfolioReturn: row.portfolio_return,
        yieldPct: row.yield_pct,
        balance: row.balance,
        income: row.income
      })) ?? []
    );
  }

  function buildGrowthRows(result: BacktestRunResult | null): GrowthRow[] {
    return result?.equity_curve ?? [];
  }

  function buildChartPoints(rows: GrowthRow[], min: number, max: number): ChartPoint[] {
    const range = Math.max(max - min, 1);
    const step = rows.length > 1 ? chartPlotWidth / (rows.length - 1) : chartPlotWidth;

    return rows.map((row, index) => {
      const x = Math.round(chartLeft + index * step);
      const y = Math.round(chartBottom - ((row.portfolio - min) / range) * chartPlotHeight);

      return {
        ...row,
        x,
        y
      };
    });
  }

  function buildValueScale(min: number, max: number): ValueScale {
    if (min === max) {
      const padding = Math.max(Math.round(max * 0.05), 100000);
      return {
        min: Math.max(0, min - padding),
        max: max + padding
      };
    }

    const range = max - min;
    const padding = range * 0.08;
    const rawMin = Math.max(0, min - padding);
    const rawMax = max + padding;
    const step = getNiceStep((rawMax - rawMin) / 4);

    return {
      min: Math.floor(rawMin / step) * step,
      max: Math.ceil(rawMax / step) * step
    };
  }

  function buildYAxisTicks(min: number, max: number): ChartTick[] {
    const range = Math.max(max - min, 1);
    const tickCount = 5;

    return Array.from({ length: tickCount }, (_, index) => {
      const value = max - (range / (tickCount - 1)) * index;
      const y = chartBottom - ((value - min) / range) * chartPlotHeight;

      return {
        label: formatCompactKrw(Math.round(value)),
        y: Math.round(y)
      };
    });
  }

  function buildXAxisTicks(rows: GrowthRow[]): ChartTick[] {
    const lastIndex = rows.length - 1;
    const interval = getMonthTickInterval(rows.length);
    const ticks = rows
      .map((row, index) => ({ row, index }))
      .filter(({ index }) => index === 0 || index === lastIndex || index % interval === 0);

    return ticks.map(({ row, index }) => ({
      label: row.label,
      x: rows.length === 1 ? chartLeft + chartPlotWidth / 2 : chartLeft + (index / lastIndex) * chartPlotWidth
    }));
  }

  function getMonthTickInterval(rowCount: number) {
    if (rowCount <= 18) return 1;
    if (rowCount <= 49) return 3;
    if (rowCount <= 85) return 6;
    return 12;
  }

  function getNiceStep(rawStep: number) {
    const magnitude = 10 ** Math.floor(Math.log10(Math.max(rawStep, 1)));
    const normalized = rawStep / magnitude;
    const multiplier = [1, 2, 2.5, 5, 10].find((item) => normalized <= item) ?? 10;

    return multiplier * magnitude;
  }

  function formatKrw(value: number) {
    return new Intl.NumberFormat('ko-KR', {
      style: 'currency',
      currency: 'KRW',
      maximumFractionDigits: 0
    }).format(value);
  }

  function formatCompactKrw(value: number) {
    const absValue = Math.abs(value);

    if (absValue >= 100000000) {
      return `${formatCompactNumber(value / 100000000)}억원`;
    }

    if (absValue >= 10000) {
      return `${formatCompactNumber(value / 10000)}만원`;
    }

    return `${formatCompactNumber(value)}원`;
  }

  function formatCompactNumber(value: number) {
    return new Intl.NumberFormat('ko-KR', {
      maximumFractionDigits: value >= 10 ? 0 : 1
    }).format(value);
  }

  function formatPercent(value: number) {
    return `${value.toFixed(1)}%`;
  }

  function formatDateTime(value: string) {
    return new Date(value).toLocaleString('ko-KR');
  }
</script>

<svelte:head>
  <title>백테스트 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">백테스트</p>
    <h1>선택한 전략을 최소 조건으로 백테스트합니다.</h1>
  </div>
</header>

{#if loading}
  <section class="state-panel">백테스트 데이터를 불러오는 중입니다.</section>
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
          <select bind:value={selectedStrategy} onchange={clearBacktestResult}>
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
          {#if selectedOption.formula}
            <code class="formula-box compact-formula">{selectedOption.formula}</code>
          {/if}
        </div>
      {/if}
    </section>

    <section class="panel backtest-panel">
      <div class="panel-heading inline">
        <div>
          <span>백테스트 조건</span>
          <strong>기간과 초기 투자금</strong>
        </div>
        <button type="button" onclick={runBacktest} disabled={backtestRunning}>
          {backtestRunning ? '실행 중' : '백테스트 실행'}
        </button>
      </div>
      <div class="backtest-form-grid compact-backtest-grid">
        <label>
          <span>시작연도</span>
          <select bind:value={startYear} onchange={clearBacktestResult}>
            <option value="2020">2020</option>
            <option value="2021">2021</option>
            <option value="2022">2022</option>
            <option value="2023">2023</option>
            <option value="2024">2024</option>
          </select>
        </label>
        <label>
          <span>종료연도</span>
          <select bind:value={endYear} onchange={clearBacktestResult}>
            <option value="2024">2024</option>
            <option value="2025">2025</option>
            <option value="2026">2026</option>
          </select>
        </label>
        <label>
          <span>초기투자금</span>
          <input bind:value={initialAmount} min="0" step="100000" type="number" onchange={clearBacktestResult} />
        </label>
      </div>
      {#if backtestError}
        <div class="empty-state error">
          <strong>백테스트 실행 불가</strong>
          <span>{backtestError}</span>
        </div>
      {:else if backtestNotice}
        <div class="empty-state">
          <strong>{backtestRunAt}</strong>
          <span>{backtestNotice}</span>
        </div>
      {:else}
        <p>전략은 위에서 선택하고, 백테스트 조건은 기간과 초기투자금만 입력합니다.</p>
      {/if}
    </section>

    <section class="panel backtest-panel">
      <div class="panel-heading">
        <span>최근 백테스트</span>
        <strong>{recentBacktests.length ? `${recentBacktests.length}개 저장됨` : '저장 결과 없음'}</strong>
      </div>
      {#if recentBacktestsError}
        <div class="empty-state error">{recentBacktestsError}</div>
      {:else if recentBacktests.length}
        <div class="table-wrap">
          <table class="compact-table wide-table">
            <caption>최근 백테스트 실행 결과</caption>
            <thead>
              <tr>
                <th>실행일</th>
                <th>전략</th>
                <th>기간</th>
                <th>초기투자금</th>
                <th>종료금액</th>
              </tr>
            </thead>
            <tbody>
              {#each recentBacktests as row}
                <tr>
                  <td>{formatDateTime(row.created_at)}</td>
                  <td>
                    <strong>{row.strategy_name}</strong>
                    <span>{row.strategy_code}</span>
                  </td>
                  <td>{row.period}</td>
                  <td>{formatKrw(row.initial_amount)}</td>
                  <td>{formatKrw(row.final_amount)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <p>백테스트를 실행하면 결과 요약이 여기에 저장됩니다.</p>
      {/if}
    </section>

    {#if hasBacktestResult}
      <section class="panel backtest-panel">
        <div class="panel-heading">
          <span>리밸런싱 이력</span>
          <strong>전략 실행 결과</strong>
        </div>
        <div class="table-wrap">
          <table class="compact-table rebalance-table">
            <thead>
              <tr>
                <th>시점</th>
                <th>보유 종목 수</th>
                <th>신규 편입</th>
                <th>제외</th>
                <th>회전율</th>
              </tr>
            </thead>
            <tbody>
              {#each rebalanceRows as row}
                <tr>
                  <td>{row.date}</td>
                  <td>{row.holdings}</td>
                  <td>{row.entries}</td>
                  <td>{row.exits}</td>
                  <td>{row.turnover}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel backtest-panel">
        <div class="panel-heading">
          <span>성과 요약</span>
          <strong>{backtestResult?.period ?? `${startYear} ~ ${endYear}`}</strong>
        </div>
        <div class="table-wrap">
          <table class="compact-table">
            <caption>백테스트 성과 지표</caption>
            <thead>
              <tr>
                <th>지표</th>
                <th>결과</th>
              </tr>
            </thead>
            <tbody>
              {#each performanceRows as row}
                <tr>
                  <th scope="row" title={metricDescriptions[row.metric] ?? ''}>{row.metric}</th>
                  <td>{row.value}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel backtest-panel">
        <div class="panel-heading">
          <span>자산 성장</span>
          <strong>{formatKrw(backtestResult?.initial_amount ?? initialAmountValue)} 투자 기준</strong>
        </div>
        <p>초기 투자금 {formatKrw(backtestResult?.initial_amount ?? initialAmountValue)} 기준으로 월별 평가금 흐름을 표시합니다.</p>
        <div class="growth-chart" aria-label="자산 성장">
          <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img">
            <title>자산 성장</title>
            <text class="chart-title" x={chartWidth / 2} y="18" text-anchor="middle">포트폴리오 평가금액</text>
            {#each growthYAxisTicks as tick}
              <line class="chart-grid-line" x1={chartLeft} x2={chartWidth - chartRight} y1={tick.y} y2={tick.y}></line>
              <text class="chart-axis-label y-axis-label" x={chartLeft - 10} y={(tick.y ?? 0) + 4} text-anchor="end">
                {tick.label}
              </text>
            {/each}
            {#each growthXAxisTicks as tick}
              <line class="chart-grid-line vertical" x1={tick.x} x2={tick.x} y1={chartTop} y2={chartBottom}></line>
              <text
                class="chart-axis-label x-axis-label"
                transform={`translate(${tick.x}, ${chartBottom + 28}) rotate(-35)`}
                text-anchor="end"
              >
                {tick.label}
              </text>
            {/each}
            <line class="chart-axis-line" x1={chartLeft} x2={chartWidth - chartRight} y1={chartBottom} y2={chartBottom}></line>
            <line class="chart-axis-line" x1={chartLeft} x2={chartLeft} y1={chartTop} y2={chartBottom}></line>
            <polyline class="portfolio-line" points={portfolioLine}></polyline>
            {#each growthChartPoints as point}
              <circle class="chart-point-hitbox" cx={point.x} cy={point.y} r="7">
                <title>{point.label} · {formatKrw(point.portfolio)}</title>
              </circle>
            {/each}
            {#if growthChartPoints.length}
              <circle
                class="chart-end-point"
                cx={growthChartPoints[growthChartPoints.length - 1].x}
                cy={growthChartPoints[growthChartPoints.length - 1].y}
                r="4"
              ></circle>
            {/if}
            <g class="chart-svg-legend">
              <line x1={chartWidth - 150} x2={chartWidth - 118} y1="18" y2="18"></line>
              <text x={chartWidth - 110} y="22">선택 전략</text>
            </g>
          </svg>
        </div>
      </section>

      <section class="panel backtest-panel">
        <div class="panel-heading">
          <span>연도별 수익률</span>
          <strong>수익률과 평가금</strong>
        </div>
        <div class="table-wrap">
          <table class="compact-table wide-table">
            <caption>연도별 백테스트 결과</caption>
            <thead>
              <tr>
                <th>연도</th>
                <th>수익률</th>
                <th>평가금</th>
                <th>인컴 수익률</th>
                <th>인컴 금액</th>
              </tr>
            </thead>
            <tbody>
              {#each annualRows as row}
                <tr>
                  <td>{row.year}</td>
                  <td class:tone-positive={row.portfolioReturn >= 0} class:tone-caution={row.portfolioReturn < 0}>
                    <strong>{row.portfolioReturn}%</strong>
                  </td>
                  <td>{formatKrw(row.balance)}</td>
                  <td>{row.yieldPct}%</td>
                  <td>{formatKrw(row.income)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>

    {:else}
      <section class="state-panel">백테스트를 실행하면 결과 블록이 아래에 표시됩니다.</section>
    {/if}
  </div>
{/if}
