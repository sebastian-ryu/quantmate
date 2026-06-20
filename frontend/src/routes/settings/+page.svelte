<script lang="ts">
  import { onMount } from 'svelte';
  import {
    fetchDashboard,
    fetchDataStatus,
    type Dashboard,
    type DataStatus
  } from '$lib/api';

  let dashboard: Dashboard | null = null;
  let dataStatus: DataStatus | null = null;
  let loading = true;
  let error = '';

  onMount(async () => {
    try {
      [dashboard, dataStatus] = await Promise.all([fetchDashboard(), fetchDataStatus()]);
    } catch (err) {
      error = err instanceof Error ? err.message : '설정 상태를 불러오지 못했습니다.';
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>환경설정 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">환경설정</p>
    <h1>API 권한, 데이터베이스, 실행 모드를 한 곳에서 점검합니다.</h1>
  </div>
</header>

{#if loading}
  <section class="state-panel">설정을 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else if dashboard && dataStatus}
  <section class="summary-grid">
    <article class="panel">
      <div class="panel-heading">
        <span>로컬 DB</span>
        <strong>{dataStatus.message}</strong>
      </div>
      <span class:ready={dataStatus.connected} class:blocked={!dataStatus.connected} class="status-pill">
        {dataStatus.connected ? '연결됨' : '확인 필요'}
      </span>
      <div class="metrics">
        {#each Object.entries(dataStatus.table_counts) as [name, count]}
          <div>
            <span>{name}</span>
            <strong>{count}</strong>
          </div>
        {/each}
      </div>
    </article>

  </section>

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

  <section class="panel">
    <div class="panel-heading">
      <span>데이터/API 권한</span>
      <strong>연동 전 점검</strong>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>소스</th>
            <th>범위</th>
            <th>상태</th>
            <th>다음 작업</th>
          </tr>
        </thead>
        <tbody>
          {#each dataStatus.provider_status as source}
            <tr>
              <td><strong>{source.name}</strong></td>
              <td>{source.scope}</td>
              <td>
                <span class:ready={source.ready} class:blocked={!source.ready} class="status-pill">
                  {source.status}
                </span>
              </td>
              <td>{source.ready ? '수집 모듈 연결' : '사용자와 권한 정보 확인'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>
{/if}
