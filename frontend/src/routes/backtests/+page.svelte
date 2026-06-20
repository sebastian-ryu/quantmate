<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchDashboard, type Dashboard } from '$lib/api';

  let dashboard: Dashboard | null = null;
  let selectedStrategy = 'momentum-core';
  let loading = true;
  let error = '';

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
          <div class:tone-positive={metric.tone === 'positive'} class:tone-caution={metric.tone === 'caution'}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </div>
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
