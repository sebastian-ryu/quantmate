<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchDashboard, type Dashboard } from '$lib/api';

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
      selectedStrategy = dashboard.backtest.strategy_code;
    } catch (err) {
      error = err instanceof Error ? err.message : '백테스트 데이터를 불러오지 못했습니다.';
    } finally {
      loading = false;
    }
  });

  $: maxEquity = Math.max(...(dashboard?.backtest.equity_curve.map((point) => point.value) ?? [100]));
  $: strategy = dashboard?.strategies.find((item) => item.code === selectedStrategy);
</script>

<svelte:head>
  <title>백테스트 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">백테스트</p>
    <h1>전략 성과와 가정을 분리해서 검토합니다.</h1>
  </div>
  <a class="button secondary" href="/recommendations">추천 결과 보기</a>
</header>

{#if loading}
  <section class="state-panel">백테스트를 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else if dashboard}
  <section class="toolbar" aria-label="백테스트 전략 선택">
    <label for="backtest-strategy">전략</label>
    <select id="backtest-strategy" bind:value={selectedStrategy}>
      {#each dashboard.strategies as item}
        <option value={item.code}>{item.name} · {item.style}</option>
      {/each}
    </select>
    <span>현재 결과는 {dashboard.backtest.strategy_code} 샘플 기준입니다.</span>
  </section>

  <section class="summary-grid">
    <article class="panel">
      <div class="panel-heading">
        <span>성과 지표</span>
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

    <article class="panel">
      <div class="panel-heading">
        <span>전략 설명</span>
        <strong>{strategy?.name ?? '전략 선택 필요'}</strong>
      </div>
      <p>{strategy?.summary ?? '선택한 전략 정보가 없습니다.'}</p>
      <ul class="assumptions">
        {#each strategy?.risk_notes ?? [] as note}
          <li>{note}</li>
        {/each}
      </ul>
    </article>
  </section>

  <section class="panel">
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
  </section>
{/if}
