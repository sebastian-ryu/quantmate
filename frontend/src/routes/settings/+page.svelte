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
      error = err instanceof Error ? err.message : '설정 상태를 불러오지 못했습니다.';
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>설정 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">로컬 설정</p>
    <h1>API, 데이터베이스, 매매 모드를 한 곳에서 점검합니다.</h1>
  </div>
  <a class="button secondary" href="/universe">데이터 상태 보기</a>
</header>

{#if loading}
  <section class="state-panel">설정을 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else if dashboard}
  <section class="content-grid">
    <article class="panel">
      <div class="panel-heading">
        <span>동작 모드</span>
        <strong>현재 안전 상태</strong>
      </div>
      <ul class="checklist">
        {#each dashboard.modes as mode}
          <li>
            <span>{mode.label}</span>
            <strong class:ready={mode.enabled} class:blocked={!mode.enabled} class="status-pill">
              {mode.enabled ? '활성' : '비활성'}
            </strong>
          </li>
        {/each}
      </ul>
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>인증 정보</span>
        <strong>.env에서 관리</strong>
      </div>
      <ul class="checklist">
        <li><span>KIS_APP_KEY</span><strong class="status-pill blocked">필요</strong></li>
        <li><span>KIS_APP_SECRET</span><strong class="status-pill blocked">필요</strong></li>
        <li><span>LIVE_TRADING_ENABLED</span><strong class="status-pill ready">기본 false</strong></li>
      </ul>
    </article>
  </section>
{/if}

