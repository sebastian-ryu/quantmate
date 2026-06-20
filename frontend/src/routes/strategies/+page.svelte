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
  $: selectedOption =
    strategyOptions.find((item) => item.code === selectedStrategy) ?? strategyOptions[0] ?? null;
  $: annualRows = buildAnnualRows(initialAmount);
  $: growthRows = buildGrowthRows(initialAmount);
  $: rebalanceRows = buildRebalanceRows();
  $: incomeRows = annualRows.map((row) => ({
    year: row.year,
    income: row.income,
    yieldPct: row.yieldPct
  }));
  $: performanceRows = buildPerformanceRows(initialAmount);
  $: growthValues = growthRows.map((row) => row.portfolio);
  $: growthMin = Math.min(...growthValues, initialAmount);
  $: growthMax = Math.max(...growthValues, initialAmount);
  $: portfolioLine = buildLinePoints(growthValues, growthMin, growthMax);
  $: incomeMax = Math.max(...incomeRows.map((row) => row.income), 1);

  function toBaseStrategyOption(strategy: Strategy): StrategyOption {
    return {
      code: strategy.code,
      name: strategy.name,
      style: strategy.style,
      source: '기본 제공 전략',
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
      summary: strategy.summary,
      dataRequirements: ['검색기 조건식', '검색 결과 후보군', '백테스트용 가격 데이터'],
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
    backtestNotice = '선택한 전략과 백테스트 조건으로 샘플 결과를 생성했습니다. 실제 실행은 일봉 데이터와 백테스트 엔진 연결 후 서버에서 계산합니다.';
  }

  function clearBacktestResult() {
    hasBacktestResult = false;
    backtestRunAt = '';
    backtestNotice = '';
  }

  function buildAnnualRows(amount: number) {
    let balance = amount;

    return annualReturnTemplate.map((row) => {
      balance *= 1 + row.portfolioReturn / 100;

      return {
        ...row,
        balance: Math.round(balance),
        income: Math.round(balance * (row.yieldPct / 100))
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

    return baseCurve.map((point) => ({
      label: point.day,
      portfolio: Math.round(amount * (point.value / 100))
    }));
  }

  function buildPerformanceRows(amount: number): PerformanceRow[] {
    const finalPortfolio = annualRows.at(-1)?.balance ?? amount;

    return [
      { metric: '시작금액', value: formatKrw(amount) },
      { metric: '종료금액', value: formatKrw(finalPortfolio) },
      { metric: '연평균 수익률(CAGR)', value: '18.4%' },
      { metric: '변동성', value: '13.7%' },
      { metric: '최고 연도', value: '18.4%' },
      { metric: '최저 연도', value: '-8.6%' },
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
    <h1>전략을 선택하고 최소 조건으로 백테스트합니다.</h1>
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
        <span>전략 선택</span>
        <strong>{selectedOption?.name ?? '전략 선택 필요'}</strong>
      </div>
      <div class="backtest-form-grid strategy-select-grid">
        <label>
          <span>전략</span>
          <select bind:value={selectedStrategy} onchange={clearBacktestResult}>
            {#each strategyOptions as item}
              <option value={item.code}>{strategyLabel(item)}</option>
            {/each}
          </select>
        </label>
      </div>
      {#if selectedOption}
        <div class="strategy-note">
          <strong>{selectedOption.style}</strong>
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
        <p>초기 투자금 {formatKrw(initialAmount)} 기준으로 선택한 전략의 자산 성장을 표시합니다.</p>
        <div class="growth-chart" aria-label="자산 성장">
          <svg viewBox="0 0 680 260" role="img">
            <title>자산 성장</title>
            <polyline class="portfolio-line" points={portfolioLine}></polyline>
          </svg>
          <div class="chart-legend">
            <span><b class="legend-dot portfolio"></b>선택 전략</span>
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

      <section class="panel backtest-panel">
        <div class="panel-heading">
          <span>포트폴리오 인컴</span>
          <strong>배당/분배금 흐름</strong>
        </div>
        <div class="income-chart" aria-label="포트폴리오 인컴">
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
                <th>연도</th>
                <th>인컴 금액</th>
                <th>인컴 수익률</th>
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
    {:else}
      <section class="state-panel">백테스트를 실행하면 결과 블록이 아래에 표시됩니다.</section>
    {/if}
  </div>
{/if}
