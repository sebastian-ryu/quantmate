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

  let dashboard: Dashboard | null = null;
  let selectedStrategy = 'momentum-core';
  let registeredStrategies: StrategyDraft[] = [];
  let backtestRunAt = '';
  let backtestNotice = '';
  let loading = true;
  let error = '';

  const metricDescriptions: Record<string, string> = {
    CAGR: '연평균 복리 수익률입니다. 기간 전체 수익을 1년 단위 성장률로 환산합니다.',
    MDD: '최고점 대비 최대 하락률입니다. 전략이 겪은 가장 큰 낙폭을 봅니다.',
    변동성: '수익률이 흔들리는 정도입니다. 높을수록 손익 변동이 큽니다.',
    승률: '전체 매매 중 이익으로 끝난 비율입니다. 손익비와 함께 봐야 합니다.',
    회전율: '포트폴리오가 얼마나 자주 교체되는지 보여줍니다. 높을수록 비용 영향이 커집니다.'
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
  $: maxEquity = Math.max(...(dashboard?.backtest.equity_curve.map((point) => point.value) ?? [100]));

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
    backtestRunAt = new Date().toLocaleString('ko-KR');
    backtestNotice = isRegisteredStrategy
      ? '검색기 등록 전략 기준의 샘플 백테스트를 표시했습니다. 실제 조건식 실행은 DB 저장과 백테스트 입력 연결 후 활성화합니다.'
      : '선택한 기본 전략 기준의 샘플 백테스트를 표시했습니다. 실제 일봉 데이터 연결 후 서버 실행으로 바꿉니다.';
  }

  function clearBacktestNotice() {
    backtestRunAt = '';
    backtestNotice = '';
  }
</script>

<svelte:head>
  <title>전략/백테스트 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">전략/백테스트</p>
    <h1>전략을 고르고 설명과 성과를 함께 검토합니다.</h1>
  </div>
  <a class="button secondary" href="/screener">검색기에서 전략 등록</a>
</header>

{#if loading}
  <section class="state-panel">전략과 백테스트를 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else if dashboard}
  <section class="toolbar" aria-label="전략 선택">
    <label for="strategy-backtest">전략</label>
    <select id="strategy-backtest" bind:value={selectedStrategy} onchange={clearBacktestNotice}>
      {#each strategyOptions as item}
        <option value={item.code}>{strategyLabel(item)}</option>
      {/each}
    </select>
    <span>{selectedOption?.source ?? '전략 선택 필요'} · 현재 백테스트는 샘플 데이터 기준입니다.</span>
  </section>

  <section class="summary-grid">
    <article class="panel">
      <div class="panel-heading">
        <span>전략 소개</span>
        <strong>{selectedOption?.name ?? '전략 선택 필요'}</strong>
      </div>
      <p>{selectedOption?.summary ?? '선택한 전략 정보가 없습니다.'}</p>
      {#if selectedOption}
        <div class="tag-row">
          <span>{selectedOption.source}</span>
          {#each selectedOption.dataRequirements as requirement}
            <span>{requirement}</span>
          {/each}
        </div>
        {#if selectedOption.formula}
          <code class="formula-box compact-formula">{selectedOption.formula}</code>
        {/if}
        <ul class="assumptions">
          {#each selectedOption.riskNotes as note}
            <li>{note}</li>
          {/each}
        </ul>
      {/if}
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>백테스트 성과</span>
        <strong>{dashboard.backtest.period}</strong>
      </div>
      <div class="metrics">
        {#each dashboard.backtest.metrics as metric}
          <button
            type="button"
            class:tone-positive={metric.tone === 'positive'}
            class:tone-caution={metric.tone === 'caution'}
            class="metric-card tooltip-anchor"
            aria-label={`${metric.label}: ${metricDescriptions[metric.label] ?? '백테스트 성과 지표입니다.'}`}
          >
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <span class="tooltip" role="tooltip">
              {metricDescriptions[metric.label] ?? '백테스트 성과 지표입니다.'}
            </span>
          </button>
        {/each}
      </div>
    </article>
  </section>

  <section class="content-grid">
    <article class="panel">
      <div class="panel-heading inline">
        <div>
          <span>백테스트 실행</span>
          <strong>{selectedOption?.name ?? dashboard.backtest.strategy_code}</strong>
        </div>
        <button type="button" onclick={runBacktest}>백테스트 실행</button>
      </div>
      {#if backtestNotice}
        <div class="empty-state">
          <strong>{backtestRunAt}</strong>
          <span>{backtestNotice}</span>
        </div>
      {:else if isRegisteredStrategy}
        <p>검색기에서 등록한 전략입니다. 현재는 샘플 백테스트로 확인하고, 실제 조건식 실행은 다음 구현 단계에서 연결합니다.</p>
      {:else}
        <p>현재는 샘플 백테스트 결과를 보여줍니다. 실제 일봉 데이터 연결 후 선택한 전략 코드로 실행되도록 확장합니다.</p>
      {/if}
      <ul class="assumptions">
        {#each dashboard.backtest.assumptions as assumption}
          <li>{assumption}</li>
        {/each}
      </ul>
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>자산 곡선</span>
        <strong>{dashboard.backtest.strategy_code}</strong>
      </div>
      <div class="chart" aria-label="백테스트 자산 곡선">
        {#each dashboard.backtest.equity_curve as point}
          <div>
            <span style={`height: ${(point.value / maxEquity) * 100}%`}></span>
            <small>{point.day}</small>
          </div>
        {/each}
      </div>
    </article>
  </section>
{/if}
