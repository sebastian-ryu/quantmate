<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchDashboard, type Dashboard } from '$lib/api';

  let dashboard: Dashboard | null = null;
  let loading = true;
  let error = '';

  onMount(async () => {
    try {
      dashboard = await fetchDashboard();
    } catch (err) {
      error = err instanceof Error ? err.message : '백테스트 데이터를 불러오지 못했습니다.';
    } finally {
      loading = false;
    }
  });

  $: maxEquity = Math.max(...(dashboard?.backtest.equity_curve.map((point) => point.value) ?? [100]));
</script>

<svelte:head>
  <title>백테스트 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">백테스트</p>
    <h1>전략 성과와 가정을 분리해서 검토합니다.</h1>
  </div>
  <button type="button">새 백테스트</button>
</header>

{#if loading}
  <section class="state-panel">백테스트를 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else if dashboard}
  <section class="summary-grid">
    <article class="panel">
      <div class="panel-heading">
        <span>성과 지표</span>
        <strong>{dashboard.backtest.period}</strong>
      </div>
      <div class="metrics">
        {#each dashboard.backtest.metrics as metric}
          <div class:tone-positive={metric.tone === 'positive'} class:tone-caution={metric.tone === 'caution'}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </div>
        {/each}
      </div>
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>가정</span>
        <strong>검토 필요</strong>
      </div>
      <ul>
        {#each dashboard.backtest.assumptions as assumption}
          <li>{assumption}</li>
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
  </section>
{/if}

