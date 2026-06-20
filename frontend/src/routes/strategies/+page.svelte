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
      error = err instanceof Error ? err.message : '전략 데이터를 불러오지 못했습니다.';
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>전략 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">전략 카탈로그</p>
    <h1>기본 제공 전략과 필요한 데이터를 확인합니다.</h1>
  </div>
  <a class="button secondary" href="/">대시보드로 이동</a>
</header>

{#if loading}
  <section class="state-panel">전략을 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else if dashboard}
  <section class="three-grid">
    {#each dashboard.strategies as strategy}
      <article class="panel">
        <div class="panel-heading">
          <span>{strategy.style}</span>
          <strong>{strategy.name}</strong>
        </div>
        <p>{strategy.summary}</p>
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
      </article>
    {/each}
  </section>
{/if}

