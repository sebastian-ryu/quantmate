<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchDashboard, type Dashboard, type Strategy } from '$lib/api';
  import { loadStrategyDrafts, type StrategyDraft } from '$lib/strategy-drafts';

  type StrategyOption = {
    code: string;
    name: string;
    style: string;
    source: string;
    summary: string;
    dataRequirements: string[];
    riskNotes: string[];
    formula?: string;
    resultCount?: number;
  };

  type AllocationRow = {
    id: number;
    symbol: string;
    name: string;
    allocation: number;
  };

  type AnnualReturnTemplate = {
    year: string;
    portfolioReturn: number;
    benchmarkReturn: number;
    yieldPct: number;
  };

  let dashboard: Dashboard | null = null;
  let selectedStrategy = 'momentum-core';
  let registeredStrategies: StrategyDraft[] = [];
  let loading = true;
  let error = '';

  let timePeriod = 'custom';
  let startYear = '2023';
  let startMonth = '1';
  let endYear = '2025';
  let endMonth = '12';
  let initialAmount = 10000000;
  let cashflowType = 'none';
  let cashflowAmount = 0;
  let cashflowFrequency = 'monthly';
  let rebalanceType = 'monthly';
  let benchmark = 'KOSPI 200';
  let reinvestDividends = 'true';
  let showIncome = 'true';
  let commissionRate = 0.015;
  let slippageRate = 0.05;
  let hasBacktestResult = false;
  let backtestRunAt = '';
  let backtestNotice = '';

  let allocationRows: AllocationRow[] = [
    { id: 1, symbol: '005930', name: '삼성전자', allocation: 40 },
    { id: 2, symbol: '000660', name: 'SK하이닉스', allocation: 20 },
    { id: 3, symbol: '005380', name: '현대차', allocation: 20 },
    { id: 4, symbol: '069500', name: 'KODEX 200', allocation: 20 }
  ];

  const annualReturnTemplate: AnnualReturnTemplate[] = [
    { year: '2021', portfolioReturn: 11.8, benchmarkReturn: 7.4, yieldPct: 1.5 },
    { year: '2022', portfolioReturn: -8.6, benchmarkReturn: -17.2, yieldPct: 1.8 },
    { year: '2023', portfolioReturn: 18.4, benchmarkReturn: 14.1, yieldPct: 1.9 },
    { year: '2024', portfolioReturn: 13.2, benchmarkReturn: 9.7, yieldPct: 2.1 },
    { year: '2025', portfolioReturn: 9.6, benchmarkReturn: 6.3, yieldPct: 2.3 }
  ];

  const metricDescriptions: Record<string, string> = {
    'Start Balance': '백테스트 시작 시점의 투자금입니다.',
    'End Balance': '백테스트 종료 시점의 평가금입니다.',
    'Annualized Return (CAGR)': '전체 기간 수익률을 연평균 복리 수익률로 환산한 값입니다.',
    'Standard Deviation': '월간 수익률 변동성을 연율화한 값입니다.',
    'Best Year': '백테스트 기간 중 가장 높은 연간 수익률입니다.',
    'Worst Year': '백테스트 기간 중 가장 낮은 연간 수익률입니다.',
    'Maximum Drawdown': '최고점 대비 가장 크게 하락한 구간의 손실률입니다.',
    'Sharpe Ratio': '변동성 대비 초과수익을 나타내는 위험조정 성과 지표입니다.',
    'Sortino Ratio': '하락 변동성만 기준으로 본 위험조정 성과 지표입니다.',
    'Turnover': '월평균 포트폴리오 교체 비율입니다.'
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
  $: selectedOption =
    strategyOptions.find((item) => item.code === selectedStrategy) ?? strategyOptions[0] ?? null;
  $: isRegisteredStrategy = selectedOption?.source === '검색기 등록 전략';
  $: totalAllocation = allocationRows.reduce((sum, row) => sum + Number(row.allocation || 0), 0);
  $: annualRows = buildAnnualRows(initialAmount);
  $: growthRows = buildGrowthRows(initialAmount);
  $: incomeRows = annualRows.map((row) => ({
    year: row.year,
    income: row.income,
    yieldPct: row.yieldPct
  }));
  $: performanceRows = buildPerformanceRows(initialAmount);
  $: growthValues = growthRows.flatMap((row) => [row.portfolio, row.benchmark]);
  $: growthMin = Math.min(...growthValues, initialAmount);
  $: growthMax = Math.max(...growthValues, initialAmount);
  $: portfolioLine = buildLinePoints(
    growthRows.map((row) => row.portfolio),
    growthMin,
    growthMax
  );
  $: benchmarkLine = buildLinePoints(
    growthRows.map((row) => row.benchmark),
    growthMin,
    growthMax
  );
  $: incomeMax = Math.max(...incomeRows.map((row) => row.income), 1);

  function toBaseStrategyOption(strategy: Strategy): StrategyOption {
    return {
      code: strategy.code,
      name: strategy.name,
      style: strategy.style,
      source: '기본 제공 전략',
      summary: strategy.summary,
      dataRequirements: strategy.data_requirements,
      riskNotes: strategy.risk_notes
    };
  }

  function toDraftStrategyOption(strategy: StrategyDraft): StrategyOption {
    return {
      code: `draft:${strategy.id}`,
      name: strategy.name,
      style: '검색식 기반',
      source: '검색기 등록 전략',
      summary: strategy.summary,
      dataRequirements: ['검색기 조건식', '검색 결과 후보군', '백테스트용 가격 데이터'],
      riskNotes: ['현재는 브라우저 로컬 저장소에만 저장됩니다.', '실제 백테스트 입력 연결은 다음 구현 단계입니다.'],
      formula: strategy.formula,
      resultCount: strategy.resultCount
    };
  }

  function strategyLabel(item: StrategyOption) {
    return `${item.name} · ${item.style}`;
  }

  function runBacktest() {
    hasBacktestResult = true;
    backtestRunAt = new Date().toLocaleString('ko-KR');
    backtestNotice = isRegisteredStrategy
      ? '검색기 등록 전략 기준의 샘플 백테스트를 생성했습니다. 실제 조건식 실행은 DB 저장과 백테스트 입력 연결 후 활성화합니다.'
      : '선택한 조건 기준의 샘플 백테스트를 생성했습니다. 실제 일봉 데이터 연결 후 서버 실행으로 바꿉니다.';
  }

  function clearBacktestResult() {
    hasBacktestResult = false;
    backtestRunAt = '';
    backtestNotice = '';
  }

  function addAllocationRow() {
    const nextId = Math.max(...allocationRows.map((row) => row.id), 0) + 1;
    allocationRows = [...allocationRows, { id: nextId, symbol: '', name: '', allocation: 0 }];
    clearBacktestResult();
  }

  function removeAllocationRow(id: number) {
    if (allocationRows.length <= 1) return;
    allocationRows = allocationRows.filter((row) => row.id !== id);
    clearBacktestResult();
  }

  function buildAnnualRows(amount: number) {
    let portfolioBalance = amount;
    let benchmarkBalance = amount;

    return annualReturnTemplate.map((row) => {
      portfolioBalance *= 1 + row.portfolioReturn / 100;
      benchmarkBalance *= 1 + row.benchmarkReturn / 100;

      return {
        ...row,
        balance: Math.round(portfolioBalance),
        benchmarkBalance: Math.round(benchmarkBalance),
        income: Math.round(portfolioBalance * (row.yieldPct / 100))
      };
    });
  }

  function buildGrowthRows(amount: number) {
    const baseCurve = dashboard?.backtest.equity_curve ?? [
      { day: '1', value: 100 },
      { day: '2', value: 103 },
      { day: '3', value: 106 },
      { day: '4', value: 102 },
      { day: '5', value: 111 },
      { day: '6', value: 118 }
    ];

    return baseCurve.map((point, index) => {
      const benchmarkMultiplier = 1 + index * 0.025 + (index > 4 ? 0.02 : 0);
      return {
        label: point.day,
        portfolio: Math.round(amount * (point.value / 100)),
        benchmark: Math.round(amount * benchmarkMultiplier)
      };
    });
  }

  function buildPerformanceRows(amount: number) {
    const finalPortfolio = annualRows.at(-1)?.balance ?? amount;
    const finalBenchmark = annualRows.at(-1)?.benchmarkBalance ?? amount;

    return [
      { metric: 'Start Balance', portfolio: formatKrw(amount), benchmark: formatKrw(amount) },
      { metric: 'End Balance', portfolio: formatKrw(finalPortfolio), benchmark: formatKrw(finalBenchmark) },
      { metric: 'Annualized Return (CAGR)', portfolio: '18.4%', benchmark: '12.8%' },
      { metric: 'Standard Deviation', portfolio: '13.7%', benchmark: '16.9%' },
      { metric: 'Best Year', portfolio: '18.4%', benchmark: '14.1%' },
      { metric: 'Worst Year', portfolio: '-8.6%', benchmark: '-17.2%' },
      { metric: 'Maximum Drawdown', portfolio: '-12.7%', benchmark: '-21.5%' },
      { metric: 'Sharpe Ratio', portfolio: '0.92', benchmark: '0.61' },
      { metric: 'Sortino Ratio', portfolio: '1.38', benchmark: '0.84' },
      { metric: 'Turnover', portfolio: '월 1.8회', benchmark: 'N/A' }
    ];
  }

  function buildLinePoints(values: number[], min: number, max: number) {
    const width = 680;
    const height = 220;
    const range = Math.max(max - min, 1);
    const step = values.length > 1 ? width / (values.length - 1) : width;

    return values
      .map((value, index) => {
        const x = Math.round(index * step);
        const y = Math.round(height - ((value - min) / range) * height);
        return `${x},${y}`;
      })
      .join(' ');
  }

  function formatKrw(value: number) {
    return new Intl.NumberFormat('ko-KR', {
      style: 'currency',
      currency: 'KRW',
      maximumFractionDigits: 0
    }).format(value);
  }
</script>

<svelte:head>
  <title>전략/백테스트 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">전략/백테스트</p>
    <h1>조건을 입력하고 백테스트 결과를 검토합니다.</h1>
  </div>
  <a class="button secondary" href="/screener">검색기에서 전략 등록</a>
</header>

{#if loading}
  <section class="state-panel">전략과 백테스트를 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else if dashboard}
  <div class="backtest-stack">
    <section class="panel backtest-panel">
      <div class="panel-heading">
        <span>Portfolio Model Configuration</span>
        <strong>백테스트 조건</strong>
      </div>
      <div class="backtest-form-grid">
        <label>
          <span>전략</span>
          <select bind:value={selectedStrategy} onchange={clearBacktestResult}>
            {#each strategyOptions as item}
              <option value={item.code}>{strategyLabel(item)}</option>
            {/each}
          </select>
        </label>
        <label>
          <span>기간 방식</span>
          <select bind:value={timePeriod} onchange={clearBacktestResult}>
            <option value="custom">직접 지정</option>
            <option value="max">가능한 전체 기간</option>
            <option value="trailing-3y">최근 3년</option>
            <option value="trailing-5y">최근 5년</option>
          </select>
        </label>
        <label>
          <span>시작 연도</span>
          <select bind:value={startYear} onchange={clearBacktestResult}>
            <option value="2020">2020</option>
            <option value="2021">2021</option>
            <option value="2022">2022</option>
            <option value="2023">2023</option>
            <option value="2024">2024</option>
          </select>
        </label>
        <label>
          <span>시작 월</span>
          <select bind:value={startMonth} onchange={clearBacktestResult}>
            {#each Array.from({ length: 12 }, (_, index) => `${index + 1}`) as month}
              <option value={month}>{month}월</option>
            {/each}
          </select>
        </label>
        <label>
          <span>종료 연도</span>
          <select bind:value={endYear} onchange={clearBacktestResult}>
            <option value="2024">2024</option>
            <option value="2025">2025</option>
            <option value="2026">2026</option>
          </select>
        </label>
        <label>
          <span>종료 월</span>
          <select bind:value={endMonth} onchange={clearBacktestResult}>
            {#each Array.from({ length: 12 }, (_, index) => `${index + 1}`) as month}
              <option value={month}>{month}월</option>
            {/each}
          </select>
        </label>
        <label>
          <span>초기 투자금</span>
          <input bind:value={initialAmount} min="0" step="100000" type="number" onchange={clearBacktestResult} />
        </label>
        <label>
          <span>현금흐름</span>
          <select bind:value={cashflowType} onchange={clearBacktestResult}>
            <option value="none">없음</option>
            <option value="contribution">정기 납입</option>
            <option value="withdrawal">정기 인출</option>
          </select>
        </label>
        <label>
          <span>현금흐름 금액</span>
          <input bind:value={cashflowAmount} min="0" step="10000" type="number" onchange={clearBacktestResult} />
        </label>
        <label>
          <span>현금흐름 주기</span>
          <select bind:value={cashflowFrequency} onchange={clearBacktestResult}>
            <option value="monthly">월별</option>
            <option value="quarterly">분기별</option>
            <option value="yearly">연별</option>
          </select>
        </label>
        <label>
          <span>리밸런싱</span>
          <select bind:value={rebalanceType} onchange={clearBacktestResult}>
            <option value="none">하지 않음</option>
            <option value="monthly">월별</option>
            <option value="quarterly">분기별</option>
            <option value="yearly">연별</option>
            <option value="threshold">비중 이탈 기준</option>
          </select>
        </label>
        <label>
          <span>벤치마크</span>
          <select bind:value={benchmark} onchange={clearBacktestResult}>
            <option value="KOSPI 200">KOSPI 200</option>
            <option value="KOSDAQ 150">KOSDAQ 150</option>
            <option value="KRX 300">KRX 300</option>
            <option value="S&P 500">S&P 500</option>
          </select>
        </label>
        <label>
          <span>배당 재투자</span>
          <select bind:value={reinvestDividends} onchange={clearBacktestResult}>
            <option value="true">예</option>
            <option value="false">아니오</option>
          </select>
        </label>
        <label>
          <span>인컴 표시</span>
          <select bind:value={showIncome} onchange={clearBacktestResult}>
            <option value="true">예</option>
            <option value="false">아니오</option>
          </select>
        </label>
        <label>
          <span>수수료(%)</span>
          <input bind:value={commissionRate} min="0" step="0.001" type="number" onchange={clearBacktestResult} />
        </label>
        <label>
          <span>슬리피지(%)</span>
          <input bind:value={slippageRate} min="0" step="0.01" type="number" onchange={clearBacktestResult} />
        </label>
      </div>
    </section>

    <section class="panel backtest-panel">
      <div class="panel-heading inline">
        <div>
          <span>Asset Allocation</span>
          <strong>자산과 비중</strong>
        </div>
        <button type="button" class="secondary" onclick={addAllocationRow}>자산 추가</button>
      </div>
      <div class="table-wrap">
        <table class="allocation-table">
          <thead>
            <tr>
              <th>종목 코드</th>
              <th>이름</th>
              <th>Portfolio 1 비중</th>
              <th>관리</th>
            </tr>
          </thead>
          <tbody>
            {#each allocationRows as row}
              <tr>
                <td>
                  <input bind:value={row.symbol} aria-label={`자산 ${row.id} 종목 코드`} onchange={clearBacktestResult} />
                </td>
                <td>
                  <input bind:value={row.name} aria-label={`자산 ${row.id} 이름`} onchange={clearBacktestResult} />
                </td>
                <td>
                  <input
                    bind:value={row.allocation}
                    aria-label={`자산 ${row.id} 비중`}
                    min="0"
                    max="100"
                    step="1"
                    type="number"
                    onchange={clearBacktestResult}
                  />
                </td>
                <td>
                  <button type="button" class="secondary" disabled={allocationRows.length <= 1} onclick={() => removeAllocationRow(row.id)}>
                    삭제
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
          <tfoot>
            <tr>
              <th colspan="2">Total allocation for portfolio 1</th>
              <td class:tone-positive={totalAllocation === 100} class:tone-caution={totalAllocation !== 100}>
                <strong>{totalAllocation}%</strong>
              </td>
              <td>{totalAllocation === 100 ? '정상' : '100%로 맞춰야 합니다.'}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      {#if selectedOption}
        <div class="strategy-note">
          <strong>{selectedOption.name}</strong>
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
          <span>Analyze Portfolios</span>
          <strong>백테스트 실행</strong>
        </div>
        <button type="button" disabled={totalAllocation !== 100} onclick={runBacktest}>백테스트 실행</button>
      </div>
      {#if totalAllocation !== 100}
        <div class="empty-state">자산 비중 합계가 100%가 되면 실행할 수 있습니다.</div>
      {:else if backtestNotice}
        <div class="empty-state">
          <strong>{backtestRunAt}</strong>
          <span>{backtestNotice}</span>
        </div>
      {:else}
        <p>조건을 입력한 뒤 실행하면 아래에 Performance Summary, Portfolio Growth, Annual Returns, Portfolio Income 결과가 표시됩니다.</p>
      {/if}
      <ul class="assumptions">
        {#each dashboard.backtest.assumptions as assumption}
          <li>{assumption}</li>
        {/each}
        {#each selectedOption?.riskNotes ?? [] as note}
          <li>{note}</li>
        {/each}
      </ul>
    </section>

    {#if hasBacktestResult}
      <section class="panel backtest-panel">
        <div class="panel-heading">
          <span>Portfolio 1</span>
          <strong>Configured assets</strong>
        </div>
        <div class="table-wrap">
          <table class="compact-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Name</th>
                <th>Allocation</th>
              </tr>
            </thead>
            <tbody>
              {#each allocationRows as row}
                <tr>
                  <td>{row.symbol || '-'}</td>
                  <td>{row.name || '-'}</td>
                  <td>{row.allocation}%</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel backtest-panel">
        <div class="panel-heading">
          <span>Performance Summary</span>
          <strong>{startYear}.{startMonth} ~ {endYear}.{endMonth}</strong>
        </div>
        <div class="table-wrap">
          <table class="compact-table">
            <caption>Portfolio performance statistics</caption>
            <thead>
              <tr>
                <th>Metric</th>
                <th>Portfolio 1</th>
                <th>{benchmark}</th>
              </tr>
            </thead>
            <tbody>
              {#each performanceRows as row}
                <tr>
                  <th scope="row" title={metricDescriptions[row.metric] ?? ''}>{row.metric}</th>
                  <td>{row.portfolio}</td>
                  <td>{row.benchmark}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel backtest-panel">
        <div class="panel-heading">
          <span>Portfolio Growth</span>
          <strong>{formatKrw(initialAmount)} invested</strong>
        </div>
        <p>
          초기 투자금 {formatKrw(initialAmount)} 기준으로 포트폴리오와 {benchmark}의 자산 성장을 비교합니다.
        </p>
        <div class="growth-chart" aria-label="Portfolio Growth">
          <svg viewBox="0 0 680 260" role="img">
            <title>Portfolio Growth</title>
            <polyline class="benchmark-line" points={benchmarkLine}></polyline>
            <polyline class="portfolio-line" points={portfolioLine}></polyline>
          </svg>
          <div class="chart-legend">
            <span><b class="legend-dot portfolio"></b>Portfolio 1</span>
            <span><b class="legend-dot benchmark"></b>{benchmark}</span>
          </div>
        </div>
        <div class="growth-axis">
          {#each growthRows as row}
            <span>{row.label}</span>
          {/each}
        </div>
      </section>

      <section class="panel backtest-panel">
        <div class="panel-heading">
          <span>Annual Returns</span>
          <strong>연도별 수익률과 잔고</strong>
        </div>
        <div class="table-wrap">
          <table class="compact-table wide-table">
            <caption>Annual returns for the configured portfolios</caption>
            <thead>
              <tr>
                <th>Year</th>
                <th>Portfolio Return</th>
                <th>Portfolio Balance</th>
                <th>Yield</th>
                <th>Income</th>
                <th>{benchmark} Return</th>
                <th>{benchmark} Balance</th>
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
                  <td class:tone-positive={row.benchmarkReturn >= 0} class:tone-caution={row.benchmarkReturn < 0}>
                    <strong>{row.benchmarkReturn}%</strong>
                  </td>
                  <td>{formatKrw(row.benchmarkBalance)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>

      {#if showIncome === 'true'}
        <section class="panel backtest-panel">
          <div class="panel-heading">
            <span>Portfolio Income</span>
            <strong>배당/분배금 흐름</strong>
          </div>
          <div class="income-chart" aria-label="Portfolio Income">
            {#each incomeRows as row}
              <div class="income-bar">
                <span style={`height: ${(row.income / incomeMax) * 100}%`}></span>
                <small>{row.year}</small>
              </div>
            {/each}
          </div>
          <div class="table-wrap">
            <table class="compact-table">
              <thead>
                <tr>
                  <th>Year</th>
                  <th>Income</th>
                  <th>Yield</th>
                </tr>
              </thead>
              <tbody>
                {#each incomeRows as row}
                  <tr>
                    <td>{row.year}</td>
                    <td>{formatKrw(row.income)}</td>
                    <td>{row.yieldPct}%</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </section>
      {/if}
    {:else}
      <section class="state-panel">
        조건 입력 후 `백테스트 실행`을 누르면 결과 블록이 아래에 표시됩니다.
      </section>
    {/if}
  </div>
{/if}
