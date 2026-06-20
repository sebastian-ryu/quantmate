<script lang="ts">
  const dataSources = [
    { name: 'KIS Open API', scope: '현재가/실시간/계좌', status: '권한 필요', ready: false },
    { name: 'FinanceDataReader', scope: '종목 목록/일봉', status: '후보', ready: true },
    { name: 'pykrx', scope: 'KRX 일봉/시장 데이터', status: '후보', ready: true },
    { name: 'OpenDART', scope: '재무제표/공시', status: 'API 키 필요', ready: false }
  ];
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
        {#each dataSources as source}
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
