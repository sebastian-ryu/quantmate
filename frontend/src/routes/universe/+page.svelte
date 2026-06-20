<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchDataStatus, type DataStatus } from '$lib/api';

  let dataStatus: DataStatus | null = null;
  let loading = true;
  let error = '';

  onMount(async () => {
    try {
      dataStatus = await fetchDataStatus();
    } catch (err) {
      error = err instanceof Error ? err.message : '데이터 상태를 불러오지 못했습니다.';
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>데이터 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">데이터 상태</p>
    <h1>종목 선정에 필요한 데이터 소스를 단계별로 연결합니다.</h1>
  </div>
  <button type="button">수집 작업 추가</button>
</header>

{#if loading}
  <section class="state-panel">데이터 상태를 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else if dataStatus}
  <section class="summary-grid">
    <article class="panel">
      <div class="panel-heading">
        <span>DB 연결</span>
        <strong>{dataStatus.message}</strong>
      </div>
      <span class:ready={dataStatus.connected} class:blocked={!dataStatus.connected} class="status-pill">
        {dataStatus.connected ? '연결됨' : '확인 필요'}
      </span>
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>저장 데이터</span>
        <strong>테이블 건수</strong>
      </div>
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

  <section class="panel">
    <div class="panel-heading">
      <span>데이터 소스</span>
      <strong>초기 연결 계획</strong>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>소스</th>
            <th>용도</th>
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
              <td>{source.ready ? '수집 모듈 구현' : '사용자와 권한 확인'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>
{/if}
