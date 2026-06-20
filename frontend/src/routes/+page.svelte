<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchDashboard, type Dashboard, type Strategy } from '$lib/api';

  let dashboard: Dashboard | null = null;
  let selectedStrategy = 'momentum-core';
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
    try {
      dashboard = await fetchDashboard();
      selectedStrategy = dashboard.strategies[0]?.code ?? selectedStrategy;
    } catch (err) {
      error = err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.';
    } finally {
      loading = false;
    }
  });

  $: strategies = dashboard?.strategies ?? [];
  $: strategy = strategies.find((item) => item.code === selectedStrategy) ?? strategies[0];
  $: recommendations =
    dashboard?.recommendations.filter(
      (item) => item.strategy_code === selectedStrategy || selectedStrategy === 'all'
    ) ?? [];
  $: maxEquity = Math.max(...(dashboard?.backtest.equity_curve.map((point) => point.value) ?? [100]));

  function strategyLabel(item: Strategy) {
    return `${item.name} · ${item.style}`;
  }
</script>

<svelte:head>
  <title>QuantMate 리서치 대시보드</title>
  <meta
    name="description"
    content="한국 주식 전략 후보, 전략 설명, 백테스트 요약을 확인하는 QuantMate 대시보드"
  />
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">한국 주식 리서치</p>
    <h1>전략 후보와 백테스트를 한 화면에서 확인합니다.</h1>
  </div>
  <div class="mode-strip" aria-label="동작 모드">
    {#each dashboard?.modes ?? [] as mode}
      <span class:enabled={mode.enabled}>{mode.label}</span>
    {/each}
  </div>
</header>

{#if loading}
  <section class="state-panel">데이터를 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">
    <strong>API 연결이 필요합니다.</strong>
    <span>{error}</span>
  </section>
{:else if dashboard}
  <section class="toolbar" aria-label="전략 선택">
    <label for="strategy">전략</label>
    <select id="strategy" bind:value={selectedStrategy}>
      {#each strategies as item}
        <option value={item.code}>{strategyLabel(item)}</option>
      {/each}
      <option value="all">전체 전략</option>
    </select>
    <span>기준일 {dashboard.as_of}</span>
  </section>

  <section class="summary-grid">
    <article class="panel">
      <div class="panel-heading">
        <span>선택 전략</span>
        <strong>{strategy?.name ?? '전체 전략'}</strong>
      </div>
      <p>{strategy?.summary ?? '모든 전략의 후보를 함께 봅니다.'}</p>
      {#if strategy}
        <div class="tag-row">
          {#each strategy.data_requirements as requirement}
            <span>{requirement}</span>
          {/each}
        </div>
        <ul>
          {#each strategy.risk_notes as note}
            <li>{note}</li>
          {/each}
        </ul>
      {/if}
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>백테스트 요약</span>
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
          <span>전략 후보</span>
          <strong>{recommendations.length}개 종목</strong>
        </div>
        <a class="button secondary" href="/strategy">전략에서 보기</a>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>종목</th>
              <th>시장</th>
              <th>점수</th>
              <th>신호</th>
              <th>근거</th>
              <th>리스크</th>
            </tr>
          </thead>
          <tbody>
            {#each recommendations as item}
              <tr>
                <td>
                  <strong>{item.name}</strong>
                  <span>{item.symbol}</span>
                </td>
                <td>{item.market}</td>
                <td>
                  <meter min="0" max="100" value={item.score}>{item.score}</meter>
                  <b>{item.score}</b>
                </td>
                <td>{item.signal}</td>
                <td>{item.rationale.join(' / ')}</td>
                <td>{item.risk_flags.join(' / ')}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
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
      <ul class="assumptions">
        {#each dashboard.backtest.assumptions as assumption}
          <li>{assumption}</li>
        {/each}
      </ul>
    </article>
  </section>
{/if}
