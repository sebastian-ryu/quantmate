<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchDashboard, type Dashboard, type Recommendation, type Strategy } from '$lib/api';

  let dashboard: Dashboard | null = null;
  let selectedStrategy = 'all';
  let searchTerm = '';
  let minScore = 70;
  let hideRisky = false;
  let conditionText = '';
  let generatedRules: Array<{ label: string; expression: string; status: string }> = [];
  let loading = true;
  let error = '';

  const conditionTemplates = [
    {
      keywords: ['거래대금', '거래량', '유동성'],
      label: '거래대금 증가',
      expression: 'trading_value_20d > trading_value_60d * 1.5'
    },
    {
      keywords: ['모멘텀', '상승', '추세', '이동평균'],
      label: '상승 추세',
      expression: 'close > ma_20 AND ma_20 > ma_60'
    },
    {
      keywords: ['수급', '외국인', '기관'],
      label: '기관/외국인 순매수',
      expression: 'foreign_net_buy_5d + institution_net_buy_5d > 0'
    },
    {
      keywords: ['저평가', '가치', 'pbr', 'per'],
      label: '가치 밸류에이션',
      expression: 'pbr < sector_pbr_median AND per > 0'
    },
    {
      keywords: ['재무', 'roe', '부채'],
      label: '재무 안정성',
      expression: 'roe_ttm > 10 AND debt_ratio < 150'
    }
  ];

  onMount(async () => {
    try {
      dashboard = await fetchDashboard();
    } catch (err) {
      error = err instanceof Error ? err.message : '추천 데이터를 불러오지 못했습니다.';
    } finally {
      loading = false;
    }
  });

  $: scoreFloor = Number(minScore);
  $: strategies = dashboard?.strategies ?? [];
  $: recommendations = dashboard?.recommendations ?? [];
  $: selectedStrategyInfo =
    strategies.find((strategy) => strategy.code === selectedStrategy) ?? null;
  $: normalizedSearch = searchTerm.trim().toLowerCase();
  $: filteredRecommendations = recommendations
    .filter((item) => {
      if (!normalizedSearch) return true;
      return [item.name, item.symbol, item.market, strategyName(item.strategy_code)]
        .join(' ')
        .toLowerCase()
        .includes(normalizedSearch);
    })
    .filter((item) => selectedStrategy === 'all' || item.strategy_code === selectedStrategy)
    .filter((item) => item.score >= scoreFloor)
    .filter((item) => !hideRisky || item.risk_flags.length === 0)
    .sort((left, right) => right.score - left.score);
  $: averageScore = filteredRecommendations.length
    ? Math.round(
        filteredRecommendations.reduce((total, item) => total + item.score, 0) /
          filteredRecommendations.length
      )
    : 0;
  $: topCandidate = filteredRecommendations[0] ?? null;
  $: quantExpression = generatedRules.length
    ? generatedRules.map((rule) => `(${rule.expression})`).join(' AND ')
    : '조건 초안을 생성하면 표시됩니다.';

  function strategyName(code: string) {
    return strategies.find((strategy) => strategy.code === code)?.name ?? code;
  }

  function signalTone(item: Recommendation) {
    if (item.score >= 80) return 'ready';
    if (item.score >= 70) return 'watch';
    return 'blocked';
  }

  function optionLabel(strategy: Strategy) {
    return `${strategy.name} · ${strategy.style}`;
  }

  function buildConditionDraft() {
    const normalized = conditionText.trim().toLowerCase();
    if (!normalized) {
      generatedRules = [];
      return;
    }

    const matchedRules = conditionTemplates
      .filter((template) => template.keywords.some((keyword) => normalized.includes(keyword)))
      .map((template) => ({ ...template, status: '초안' }));

    generatedRules = matchedRules.length
      ? matchedRules
      : [
          {
            label: '사용자 조건',
            expression: `custom_condition("${conditionText.trim()}")`,
            status: '수동 정의 필요'
          }
        ];
  }
</script>

<svelte:head>
  <title>추천 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">종목 추천</p>
    <h1>전략별 후보를 점수와 리스크 기준으로 좁혀 봅니다.</h1>
  </div>
  <span class="status-pill ready">샘플 신호</span>
</header>

{#if loading}
  <section class="state-panel">추천 데이터를 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else if dashboard}
  <section class="toolbar filter-toolbar" aria-label="추천 필터">
    <label>
      <span>종목</span>
      <input bind:value={searchTerm} placeholder="종목명 또는 코드" type="search" />
    </label>

    <label>
      <span>전략</span>
      <select bind:value={selectedStrategy}>
        <option value="all">전체 전략</option>
        {#each strategies as strategy}
          <option value={strategy.code}>{optionLabel(strategy)}</option>
        {/each}
      </select>
    </label>

    <label class="score-control">
      <span>최소 점수 {scoreFloor}</span>
      <input type="range" min="0" max="100" step="1" bind:value={minScore} />
    </label>

    <label class="check-control">
      <input type="checkbox" bind:checked={hideRisky} />
      <span>리스크 없는 후보만</span>
    </label>
  </section>

  <section class="content-grid">
    <article class="panel">
      <div class="panel-heading">
        <span>조건 입력</span>
        <strong>검색 조건 초안</strong>
      </div>
      <div class="condition-editor">
        <textarea
          bind:value={conditionText}
          rows="4"
          placeholder="예: 거래대금이 늘고 20일선 위에 있는 저평가 종목"
        ></textarea>
        <button type="button" onclick={buildConditionDraft}>조건 초안 만들기</button>
      </div>
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>퀀트식</span>
        <strong>빌더 초안</strong>
      </div>
      {#if generatedRules.length}
        <ul class="condition-list">
          {#each generatedRules as rule}
            <li>
              <span>{rule.label}</span>
              <strong>{rule.status}</strong>
            </li>
          {/each}
        </ul>
      {/if}
      <code class="formula-box">{quantExpression}</code>
    </article>
  </section>

  <section class="summary-grid">
    <article class="panel">
      <div class="panel-heading">
        <span>필터 결과</span>
        <strong>{filteredRecommendations.length}개 후보</strong>
      </div>
      <div class="metrics">
        <div>
          <span>평균 점수</span>
          <strong>{averageScore}</strong>
        </div>
        <div>
          <span>상위 후보</span>
          <strong>{topCandidate?.name ?? '-'}</strong>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="panel-heading">
        <span>선택 전략</span>
        <strong>{selectedStrategyInfo?.name ?? '전체 전략'}</strong>
      </div>
      <p>{selectedStrategyInfo?.summary ?? '모든 기본 전략의 후보를 함께 비교합니다.'}</p>
      {#if selectedStrategyInfo}
        <div class="tag-row">
          {#each selectedStrategyInfo.data_requirements as requirement}
            <span>{requirement}</span>
          {/each}
        </div>
      {/if}
    </article>
  </section>

  <section class="panel">
    <div class="panel-heading inline">
      <div>
        <span>추천 목록</span>
        <strong>기준일 {dashboard.as_of}</strong>
      </div>
      <a class="button secondary" href="/backtests">백테스트 보기</a>
    </div>

    {#if filteredRecommendations.length}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>순위</th>
              <th>종목</th>
              <th>전략</th>
              <th>점수</th>
              <th>신호</th>
              <th>근거</th>
              <th>리스크</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredRecommendations as item, index}
              <tr>
                <td class="rank-cell">{index + 1}</td>
                <td>
                  <strong>{item.name}</strong>
                  <span>{item.symbol} · {item.market}</span>
                </td>
                <td>{strategyName(item.strategy_code)}</td>
                <td>
                  <meter min="0" max="100" value={item.score}>{item.score}</meter>
                  <b>{item.score}</b>
                </td>
                <td>
                  <span class:ready={signalTone(item) === 'ready'} class:blocked={signalTone(item) === 'blocked'} class="status-pill">
                    {item.signal}
                  </span>
                </td>
                <td>
                  <ul class="compact-list">
                    {#each item.rationale as rationale}
                      <li>{rationale}</li>
                    {/each}
                  </ul>
                </td>
                <td>
                  <ul class="compact-list">
                    {#each item.risk_flags as risk}
                      <li>{risk}</li>
                    {/each}
                  </ul>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else}
      <div class="empty-state">현재 조건에 맞는 후보가 없습니다.</div>
    {/if}
  </section>
{/if}
