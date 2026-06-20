<script lang="ts">
  import { onMount } from 'svelte';
  import {
    fetchDashboard,
    fetchPaperConfig,
    updatePaperConfig,
    type Dashboard,
    type PaperConfig
  } from '$lib/api';

  let dashboard: Dashboard | null = null;
  let paperConfig: PaperConfig | null = null;
  let loading = true;
  let saving = false;
  let error = '';

  onMount(async () => {
    try {
      [dashboard, paperConfig] = await Promise.all([fetchDashboard(), fetchPaperConfig()]);
    } catch (err) {
      error = err instanceof Error ? err.message : '모의투자 상태를 불러오지 못했습니다.';
    } finally {
      loading = false;
    }
  });

  $: paperEnabled = paperConfig?.enabled ?? false;

  function formatKrw(value: number) {
    return `${new Intl.NumberFormat('ko-KR').format(value)}원`;
  }

  async function setPaperEnabled(enabled: boolean) {
    saving = true;
    error = '';
    try {
      paperConfig = await updatePaperConfig(enabled);
      dashboard = await fetchDashboard();
    } catch (err) {
      error = err instanceof Error ? err.message : '모의투자 설정을 저장하지 못했습니다.';
    } finally {
      saving = false;
    }
  }

  function handlePaperToggle(event: Event) {
    const target = event.currentTarget as HTMLInputElement;
    void setPaperEnabled(target.checked);
  }
</script>

<svelte:head>
  <title>모의투자 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">모의투자</p>
    <h1>백테스트를 통과한 전략 신호를 실거래 전에 검증합니다.</h1>
  </div>
  <span class:ready={paperEnabled} class:blocked={!paperEnabled} class="status-pill">
    {paperEnabled ? '사용 가능' : '비활성'}
  </span>
</header>

{#if loading}
  <section class="state-panel">모의투자 상태를 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else if dashboard && paperConfig}
  <section class="summary-grid">
    <article class="panel">
      <div class="panel-heading">
        <span>실행 옵션</span>
        <strong>{paperEnabled ? '모의투자 사용' : '모의투자 중지'}</strong>
      </div>
      <label class="switch-row">
        <span>모의투자</span>
        <input
          type="checkbox"
          role="switch"
          checked={paperEnabled}
          disabled={saving}
          onchange={handlePaperToggle}
        />
      </label>
      <p class="muted">
        {saving ? '설정을 저장하는 중입니다.' : '이 설정은 실거래 주문과 연결되지 않습니다.'}
      </p>
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>동작 모드</span>
        <strong>현재 상태</strong>
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
  </section>

  <section class="three-grid">
    <article class="panel">
      <div class="panel-heading">
        <span>계좌</span>
        <strong>시뮬레이션 계좌</strong>
      </div>
      <div class="mini-stat">
        <span>초기 자금</span>
        <strong>{formatKrw(paperConfig.initial_cash)}</strong>
      </div>
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>주문 제한</span>
        <strong>기본 안전값</strong>
      </div>
      <ul>
        <li>종목당 최대 주문 {formatKrw(paperConfig.max_order_amount)}</li>
        <li>일 최대 주문 {paperConfig.daily_order_limit}회</li>
        <li>일 손실 {formatKrw(paperConfig.daily_loss_limit)} 도달 시 중지</li>
      </ul>
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>체결 모델</span>
        <strong>{paperConfig.fill_model}</strong>
      </div>
      <p>전략 신호를 주문 후보로 바꾸는 기능은 백테스트 저장 이후 연결합니다.</p>
    </article>
  </section>
{/if}
