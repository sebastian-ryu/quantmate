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
      error = err instanceof Error ? err.message : '모의 투자 상태를 불러오지 못했습니다.';
    } finally {
      loading = false;
    }
  });

  $: paperEnabled = dashboard?.modes.find((mode) => mode.code === 'paper')?.enabled ?? false;
</script>

<svelte:head>
  <title>모의 투자 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">모의 투자</p>
    <h1>실거래 전에 신호와 주문 흐름을 안전하게 검증합니다.</h1>
  </div>
  <span class:ready={paperEnabled} class:blocked={!paperEnabled} class="status-pill">
    {paperEnabled ? '사용 가능' : '비활성'}
  </span>
</header>

{#if loading}
  <section class="state-panel">모의 투자 상태를 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else}
  <section class="three-grid">
    <article class="panel">
      <div class="panel-heading">
        <span>계좌</span>
        <strong>시뮬레이션 계좌</strong>
      </div>
      <div class="mini-stat">
        <span>초기 자금</span>
        <strong>10,000,000원</strong>
      </div>
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>주문 제한</span>
        <strong>기본 안전값</strong>
      </div>
      <ul>
        <li>종목당 최대 주문 100,000원</li>
        <li>일 최대 주문 10회</li>
        <li>일 손실 50,000원 도달 시 중지</li>
      </ul>
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>다음 구현</span>
        <strong>체결 모델</strong>
      </div>
      <p>현재 화면은 모의 투자 설정의 자리 표시자입니다. 실제 주문 시뮬레이션은 백테스트 저장 이후 연결합니다.</p>
    </article>
  </section>
{/if}

