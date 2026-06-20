<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchDashboard, type Dashboard, type Recommendation, type Strategy } from '$lib/api';
  import { loadStrategyDrafts, type StrategyDraft } from '$lib/strategy-drafts';

  type StrategyOption = {
    code: string;
    name: string;
    style: string;
    source: string;
    summary: string;
    dataRequirements: string[];
    formula?: string;
    resultCount?: number;
  };

  type CandidateRow = Recommendation & {
    displayStrategyName: string;
    displayRationale: string[];
    displayRiskFlags: string[];
  };

  let dashboard: Dashboard | null = null;
  let selectedStrategy = 'momentum-core';
  let registeredStrategies: StrategyDraft[] = [];
  let loading = true;
  let error = '';

  onMount(async () => {
    registeredStrategies = loadStrategyDrafts();

    try {
      dashboard = await fetchDashboard();
      selectedStrategy = dashboard.backtest.strategy_code;
    } catch (err) {
      error = err instanceof Error ? err.message : '전략 데이터를 불러오지 못했습니다.';
    } finally {
      loading = false;
    }
  });

  $: baseStrategies = dashboard?.strategies ?? [];
  $: recommendations = dashboard?.recommendations ?? [];
  $: strategyOptions = [
    ...baseStrategies.map(toBaseStrategyOption),
    ...registeredStrategies.map(toDraftStrategyOption)
  ];
  $: selectedOption =
    strategyOptions.find((item) => item.code === selectedStrategy) ?? strategyOptions[0] ?? null;
  $: candidateRows = buildCandidateRows(selectedOption, recommendations);
  $: averageScore = candidateRows.length
    ? Math.round(candidateRows.reduce((total, item) => total + item.score, 0) / candidateRows.length)
    : 0;

  function toBaseStrategyOption(strategy: Strategy): StrategyOption {
    return {
      code: strategy.code,
      name: strategy.name,
      style: strategy.style,
      source: '기본 제공 전략',
      summary: strategy.summary,
      dataRequirements: strategy.data_requirements
    };
  }

  function toDraftStrategyOption(strategy: StrategyDraft): StrategyOption {
    return {
      code: `draft:${strategy.id}`,
      name: strategy.name,
      style: '검색식 기반',
      source: '검색기 등록 전략',
      summary: strategy.summary,
      dataRequirements: ['검색기 조건식', '검색 결과 후보군', '백테스트용 가격 데이터'],
      formula: strategy.formula,
      resultCount: strategy.resultCount
    };
  }

  function strategyLabel(item: StrategyOption) {
    return `${item.name} · ${item.style}`;
  }

  function buildCandidateRows(option: StrategyOption | null, items: Recommendation[]): CandidateRow[] {
    if (!option) return [];

    if (option.code.startsWith('draft:')) {
      const resultLimit = option.resultCount && option.resultCount > 0 ? option.resultCount : items.length;

      return items
        .slice()
        .sort((left, right) => right.score - left.score)
        .slice(0, resultLimit)
        .map((item) => ({
          ...item,
          displayStrategyName: option.name,
          displayRationale: [option.formula ? `검색식: ${option.formula}` : option.summary, ...item.rationale.slice(0, 1)],
          displayRiskFlags: item.risk_flags
        }));
    }

    return items
      .filter((item) => item.strategy_code === option.code)
      .sort((left, right) => right.score - left.score)
      .map((item) => ({
        ...item,
        displayStrategyName: option.name,
        displayRationale: item.rationale,
        displayRiskFlags: item.risk_flags
      }));
  }

  function signalTone(item: CandidateRow) {
    if (item.score >= 80) return 'ready';
    if (item.score >= 70) return 'watch';
    return 'blocked';
  }
</script>

<svelte:head>
  <title>전략 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">전략</p>
    <h1>전략을 선택하고 해당 조건에 맞는 후보 종목을 확인합니다.</h1>
  </div>
</header>

{#if loading}
  <section class="state-panel">전략 데이터를 불러오는 중입니다.</section>
{:else if error}
  <section class="state-panel error">{error}</section>
{:else if dashboard}
  <div class="backtest-stack">
    <section class="panel backtest-panel">
      <div class="panel-heading">
        <span>전략 선택</span>
        <strong>{selectedOption?.name ?? '전략 선택 필요'}</strong>
      </div>
      <div class="backtest-form-grid strategy-select-grid">
        <label>
          <span>전략</span>
          <select bind:value={selectedStrategy}>
            {#each strategyOptions as item}
              <option value={item.code}>{strategyLabel(item)}</option>
            {/each}
          </select>
        </label>
      </div>
      {#if selectedOption}
        <div class="strategy-note">
          <strong>{selectedOption.style}</strong>
          <span>{selectedOption.summary}</span>
          <div class="tag-row">
            <span>{selectedOption.source}</span>
            {#each selectedOption.dataRequirements as requirement}
              <span>{requirement}</span>
            {/each}
          </div>
          {#if selectedOption.formula}
            <code class="formula-box compact-formula">{selectedOption.formula}</code>
          {/if}
        </div>
      {/if}
    </section>

    <section class="panel screener-results">
      <div class="panel-heading inline">
        <div>
          <span>전략 검색 결과</span>
          <strong>{candidateRows.length}개 종목</strong>
        </div>
        <span class="muted">평균 점수 {averageScore || '-'}</span>
      </div>
      <div class="table-wrap">
        <table class="wide-table strategy-result-table">
          <thead>
            <tr>
              <th>종목</th>
              <th>시장</th>
              <th>전략</th>
              <th>점수</th>
              <th>신호</th>
              <th>근거</th>
              <th>리스크</th>
            </tr>
          </thead>
          <tbody>
            {#each candidateRows as row}
              <tr>
                <td>
                  <strong>{row.name}</strong>
                  <span>{row.symbol} · {row.market}</span>
                </td>
                <td>{row.market}</td>
                <td>{row.displayStrategyName}</td>
                <td>
                  <meter min="0" max="100" value={row.score}>{row.score}</meter>
                  <b>{row.score}</b>
                </td>
                <td>
                  <span class:ready={signalTone(row) === 'ready'} class:blocked={signalTone(row) === 'blocked'} class="status-pill">
                    {row.signal}
                  </span>
                </td>
                <td>
                  <ul class="compact-list">
                    {#each row.displayRationale as rationale}
                      <li>{rationale}</li>
                    {/each}
                  </ul>
                </td>
                <td>
                  <ul class="compact-list">
                    {#each row.displayRiskFlags as risk}
                      <li>{risk}</li>
                    {:else}
                      <li>특이 리스크 없음</li>
                    {/each}
                  </ul>
                </td>
              </tr>
            {:else}
              <tr>
                <td colspan="7">
                  <div class="empty-state">현재 선택한 전략에 맞는 종목이 없습니다.</div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>
  </div>
{/if}
