<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchDashboard, type Dashboard, type Strategy } from '$lib/api';
  import { loadStrategyDrafts, type StrategyDraft } from '$lib/strategy-drafts';

  type StrategyOption = {
    code: string;
    name: string;
    style: string;
    source: string;
    sourceKind: 'system' | 'custom';
    summary: string;
    dataRequirements: string[];
    formula?: string;
    resultCount?: number;
  };

  type AnnualReturnTemplate = {
    year: string;
    portfolioReturn: number;
    yieldPct: number;
  };

  type RebalanceRow = {
    date: string;
    holdings: string;
    entries: string;
    exits: string;
    turnover: string;
  };

  type PerformanceRow = {
    metric: string;
    value: string;
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
  let selectedStrategy = 'momentum-core';
  let registeredStrategies: StrategyDraft[] = [];
  let loading = true;
  let error = '';

  let startYear = '2023';
  let endYear = '2025';
  let initialAmount = 10000000;
  let hasBacktestResult = false;
  let backtestRunAt = '';
  let backtestNotice = '';

  const annualReturnTemplate: AnnualReturnTemplate[] = [
    { year: '2021', portfolioReturn: 11.8, yieldPct: 1.5 },
    { year: '2022', portfolioReturn: -8.6, yieldPct: 1.8 },
    { year: '2023', portfolioReturn: 18.4, yieldPct: 1.9 },
    { year: '2024', portfolioReturn: 13.2, yieldPct: 2.1 },
    { year: '2025', portfolioReturn: 9.6, yieldPct: 2.3 }
  ];

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
    registeredStrategies = loadStrategyDrafts();

    try {
      dashboard = await fetchDashboard();
      selectedStrategy = dashboard.backtest.strategy_code;
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
  $: annualRows = buildAnnualRows(initialAmount, startYear, endYear);
  $: growthRows = buildGrowthRows(initialAmount, startYear, endYear);
  $: rebalanceRows = buildRebalanceRows();
  $: performanceRows = buildPerformanceRows(initialAmount);
  $: growthValues = growthRows.map((row) => row.portfolio);
  $: growthMin = Math.min(...growthValues, initialAmount);
  $: growthMax = Math.max(...growthValues, initialAmount);
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
      source: '기본 제공 전략',
      sourceKind: 'system',
      summary: strategy.summary,
      dataRequirements: strategy.data_requirements
    };
  }

  function toDraftStrategyOption(strategy: StrategyDraft): StrategyOption {
    return {
      code: `draft:${strategy.id}`,
      name: strategy.name,
      style: '검색식 기반',
      source: '검색기 등록 전략',
      sourceKind: 'custom',
      summary: strategy.summary,
      dataRequirements: ['검색기 조건식', '검색 결과 후보군', '백테스트용 가격 데이터'],
      formula: strategy.formula,
      resultCount: strategy.resultCount
    };
  }

  function strategyLabel(item: StrategyOption) {
    return `${item.name} · ${item.style}`;
  }

  function sourceBadgeLabel(item: StrategyOption) {
    return item.sourceKind === 'system' ? '시스템 제공' : '사용자 등록';
  }

  function runBacktest() {
    hasBacktestResult = true;
    backtestRunAt = new Date().toLocaleString('ko-KR');
    backtestNotice = '선택한 전략과 백테스트 조건으로 샘플 결과를 생성했습니다. 실제 실행은 일봉 데이터와 백테스트 엔진 연결 후 서버에서 계산합니다.';
  }

  function clearBacktestResult() {
    hasBacktestResult = false;
    backtestRunAt = '';
    backtestNotice = '';
  }

  function buildAnnualRows(amount: number, start: string, end: string) {
    let balance = amount;

    return getYearRange(start, end).map((year) => {
      const portfolioReturn = getAnnualReturnForYear(year);
      const yieldPct = getYieldForYear(year);
      balance *= 1 + portfolioReturn / 100;

      return {
        year: String(year),
        portfolioReturn,
        yieldPct,
        balance: Math.round(balance),
        income: Math.round(balance * (yieldPct / 100))
      };
    });
  }

  function buildGrowthRows(amount: number, start: string, end: string): GrowthRow[] {
    const startValue = Number(start);
    const endValue = Number(end);
    const from = Number.isFinite(startValue) ? startValue : new Date().getFullYear();
    const to = Number.isFinite(endValue) ? endValue : from;
    const firstYear = Math.min(from, to);
    const lastYear = Math.max(from, to);
    const monthCount = Math.max((lastYear - firstYear + 1) * 12, 1);
    let balance = amount;

    return Array.from({ length: monthCount }, (_, index) => {
      if (index > 0) {
        const previousYear = firstYear + Math.floor((index - 1) / 12);
        const annualReturn = getAnnualReturnForYear(previousYear);
        const monthDivisor = previousYear === lastYear ? 11 : 12;
        const monthlyReturn = Math.pow(1 + annualReturn / 100, 1 / monthDivisor) - 1;
        balance *= 1 + monthlyReturn;
      }

      const year = firstYear + Math.floor(index / 12);
      const month = index % 12;

      return {
        label: `${year}.${String(month + 1).padStart(2, '0')}`,
        portfolio: Math.round(balance)
      };
    });
  }

  function buildPerformanceRows(amount: number): PerformanceRow[] {
    const finalPortfolio = annualRows.at(-1)?.balance ?? amount;
    const yearCount = Math.max(annualRows.length, 1);
    const cagr = amount > 0 ? (finalPortfolio / amount) ** (1 / yearCount) - 1 : 0;
    const bestReturn = annualRows.reduce((best, row) => (row.portfolioReturn > best.portfolioReturn ? row : best), annualRows[0]);
    const worstReturn = annualRows.reduce((worst, row) => (row.portfolioReturn < worst.portfolioReturn ? row : worst), annualRows[0]);

    return [
      { metric: '시작금액', value: formatKrw(amount) },
      { metric: '종료금액', value: formatKrw(finalPortfolio) },
      { metric: '연평균 수익률(CAGR)', value: formatPercent(cagr * 100) },
      { metric: '변동성', value: '13.7%' },
      { metric: '최고 연도', value: `${bestReturn.year} · ${formatPercent(bestReturn.portfolioReturn)}` },
      { metric: '최저 연도', value: `${worstReturn.year} · ${formatPercent(worstReturn.portfolioReturn)}` },
      { metric: '최대 낙폭(MDD)', value: '-12.7%' },
      { metric: '샤프 비율', value: '0.92' },
      { metric: '소르티노 비율', value: '1.38' },
      { metric: '월평균 회전율', value: '1.8회' }
    ];
  }

  function buildRebalanceRows(): RebalanceRow[] {
    return [
      {
        date: '2025-01',
        holdings: '10종목',
        entries: '삼성전자, SK하이닉스, 현대차',
        exits: '카카오',
        turnover: '24%'
      },
      {
        date: '2025-02',
        holdings: '10종목',
        entries: 'NAVER, 셀트리온',
        exits: 'LG화학, POSCO홀딩스',
        turnover: '31%'
      },
      {
        date: '2025-03',
        holdings: '10종목',
        entries: '기아, KB금융',
        exits: '삼성SDI',
        turnover: '18%'
      },
      {
        date: '2025-04',
        holdings: '10종목',
        entries: '한화에어로스페이스',
        exits: '없음',
        turnover: '12%'
      }
    ];
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

  function getAnnualReturnForYear(year: number) {
    const matched = annualReturnTemplate.find((row) => Number(row.year) === year);
    if (matched) return matched.portfolioReturn;

    const fallbackIndex = Math.abs(year) % annualReturnTemplate.length;
    return annualReturnTemplate[fallbackIndex].portfolioReturn;
  }

  function getYieldForYear(year: number) {
    const matched = annualReturnTemplate.find((row) => Number(row.year) === year);
    if (matched) return matched.yieldPct;

    const fallbackIndex = Math.abs(year) % annualReturnTemplate.length;
    return annualReturnTemplate[fallbackIndex].yieldPct;
  }

  function getYearRange(start: string, end: string) {
    const startValue = Number(start);
    const endValue = Number(end);
    const from = Number.isFinite(startValue) ? startValue : new Date().getFullYear();
    const to = Number.isFinite(endValue) ? endValue : from;
    const firstYear = Math.min(from, to);
    const lastYear = Math.max(from, to);

    return Array.from({ length: lastYear - firstYear + 1 }, (_, index) => firstYear + index);
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
          <div class="tag-row">
            <span>{selectedOption.source}</span>
            {#each selectedOption.dataRequirements as requirement}
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
        <button type="button" onclick={runBacktest}>백테스트 실행</button>
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
      {#if backtestNotice}
        <div class="empty-state">
          <strong>{backtestRunAt}</strong>
          <span>{backtestNotice}</span>
        </div>
      {:else}
        <p>전략은 위에서 선택하고, 백테스트 조건은 기간과 초기투자금만 입력합니다.</p>
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
          <strong>{startYear} ~ {endYear}</strong>
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
          <strong>{formatKrw(initialAmount)} 투자 기준</strong>
        </div>
        <p>초기 투자금 {formatKrw(initialAmount)} 기준으로 월별 평가금 흐름을 표시합니다.</p>
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
