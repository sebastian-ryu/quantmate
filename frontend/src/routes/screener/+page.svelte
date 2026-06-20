<script lang="ts">
  type ScreenerRow = {
    symbol: string;
    name: string;
    exchange: string;
    sector: string;
    industry: string;
    marketCap: number;
    price: number;
    changePct: number;
    per: number;
    pbr: number;
    dividendYield: number;
    roe: number;
    debtRatio: number;
    momentum: number;
    fairValueUpside: number;
  };

  const rows: ScreenerRow[] = [
    {
      symbol: '005930',
      name: '삼성전자',
      exchange: 'KOSPI',
      sector: '기술',
      industry: '반도체',
      marketCap: 2247.7,
      price: 354000,
      changePct: -2.3,
      per: 14.8,
      pbr: 1.4,
      dividendYield: 1.7,
      roe: 9.8,
      debtRatio: 34,
      momentum: 82,
      fairValueUpside: 21.8
    },
    {
      symbol: '000660',
      name: 'SK하이닉스',
      exchange: 'KOSPI',
      sector: '기술',
      industry: '반도체',
      marketCap: 1957.7,
      price: 276400,
      changePct: 2.9,
      per: 18.3,
      pbr: 1.6,
      dividendYield: 0.6,
      roe: 12.2,
      debtRatio: 58,
      momentum: 78,
      fairValueUpside: 3.4
    },
    {
      symbol: '035720',
      name: '카카오',
      exchange: 'KOSPI',
      sector: '커뮤니케이션',
      industry: '인터넷 서비스',
      marketCap: 23.4,
      price: 43750,
      changePct: 1.2,
      per: 27.4,
      pbr: 1.1,
      dividendYield: 0.2,
      roe: 4.5,
      debtRatio: 71,
      momentum: 71,
      fairValueUpside: 12.1
    },
    {
      symbol: '005380',
      name: '현대차',
      exchange: 'KOSPI',
      sector: '소비순환재',
      industry: '자동차',
      marketCap: 138.6,
      price: 613000,
      changePct: 2.0,
      per: 6.2,
      pbr: 0.8,
      dividendYield: 4.1,
      roe: 14.9,
      debtRatio: 128,
      momentum: 66,
      fairValueUpside: 14.2
    },
    {
      symbol: '035420',
      name: 'NAVER',
      exchange: 'KOSPI',
      sector: '커뮤니케이션',
      industry: '인터넷 서비스',
      marketCap: 31.8,
      price: 198500,
      changePct: -0.7,
      per: 21.6,
      pbr: 1.2,
      dividendYield: 0.5,
      roe: 7.3,
      debtRatio: 44,
      momentum: 63,
      fairValueUpside: 18.7
    },
    {
      symbol: '247540',
      name: '에코프로비엠',
      exchange: 'KOSDAQ',
      sector: '소재',
      industry: '전지 소재',
      marketCap: 16.9,
      price: 173200,
      changePct: 3.8,
      per: 38.5,
      pbr: 3.9,
      dividendYield: 0.0,
      roe: 6.1,
      debtRatio: 96,
      momentum: 74,
      fairValueUpside: -8.4
    }
  ];

  const categories = [
    '인기 항목',
    '가격',
    '밸류에이션',
    '재정 상황',
    '배당',
    '성장',
    '리스크',
    '기술적 분석',
    '프로필'
  ];

  const presets = [
    { label: '대형 우량주', marketCapMin: 100, perMax: 20, debtRatioMax: 150 },
    { label: '저평가 후보', pbrMax: 1.2, perMax: 15, roeMin: 8 },
    { label: '모멘텀 후보', momentumMin: 70, changeMin: 0 },
    { label: '배당 관심주', dividendMin: 2, debtRatioMax: 180 }
  ];

  let query = '';
  let exchange = 'all';
  let sector = 'all';
  let marketCapMin = '';
  let marketCapMax = '';
  let priceMin = '';
  let priceMax = '';
  let perMax = '';
  let pbrMax = '';
  let dividendMin = '';
  let roeMin = '';
  let debtRatioMax = '';
  let momentumMin = '';
  let changeMin = '';
  let activeCategory = categories[0];
  let activePreset = '';

  $: sectors = Array.from(new Set(rows.map((row) => row.sector)));
  $: filteredRows = rows.filter((row) => {
    const normalizedQuery = query.trim().toLowerCase();
    const matchesQuery =
      !normalizedQuery ||
      [row.name, row.symbol, row.exchange, row.sector, row.industry]
        .join(' ')
        .toLowerCase()
        .includes(normalizedQuery);

    return (
      matchesQuery &&
      (exchange === 'all' || row.exchange === exchange) &&
      (sector === 'all' || row.sector === sector) &&
      passesMin(row.marketCap, marketCapMin) &&
      passesMax(row.marketCap, marketCapMax) &&
      passesMin(row.price, priceMin) &&
      passesMax(row.price, priceMax) &&
      passesMax(row.per, perMax) &&
      passesMax(row.pbr, pbrMax) &&
      passesMin(row.dividendYield, dividendMin) &&
      passesMin(row.roe, roeMin) &&
      passesMax(row.debtRatio, debtRatioMax) &&
      passesMin(row.momentum, momentumMin) &&
      passesMin(row.changePct, changeMin)
    );
  });
  $: appliedFilterCount = [
    query,
    exchange !== 'all' ? exchange : '',
    sector !== 'all' ? sector : '',
    marketCapMin,
    marketCapMax,
    priceMin,
    priceMax,
    perMax,
    pbrMax,
    dividendMin,
    roeMin,
    debtRatioMax,
    momentumMin,
    changeMin
  ].filter(Boolean).length;
  $: formulaPreview =
    [
      exchange !== 'all' ? `exchange == "${exchange}"` : '',
      sector !== 'all' ? `sector == "${sector}"` : '',
      marketCapMin ? `market_cap_trillion >= ${marketCapMin}` : '',
      marketCapMax ? `market_cap_trillion <= ${marketCapMax}` : '',
      priceMin ? `close >= ${priceMin}` : '',
      priceMax ? `close <= ${priceMax}` : '',
      perMax ? `per <= ${perMax}` : '',
      pbrMax ? `pbr <= ${pbrMax}` : '',
      dividendMin ? `dividend_yield >= ${dividendMin}` : '',
      roeMin ? `roe >= ${roeMin}` : '',
      debtRatioMax ? `debt_ratio <= ${debtRatioMax}` : '',
      momentumMin ? `momentum_score >= ${momentumMin}` : '',
      changeMin ? `daily_change_pct >= ${changeMin}` : ''
    ]
      .filter(Boolean)
      .join(' AND ') || '필터를 선택하면 조건식 초안이 표시됩니다.';

  function passesMin(value: number, filterValue: string) {
    return !filterValue || value >= Number(filterValue);
  }

  function passesMax(value: number, filterValue: string) {
    return !filterValue || value <= Number(filterValue);
  }

  function resetFilters() {
    query = '';
    exchange = 'all';
    sector = 'all';
    marketCapMin = '';
    marketCapMax = '';
    priceMin = '';
    priceMax = '';
    perMax = '';
    pbrMax = '';
    dividendMin = '';
    roeMin = '';
    debtRatioMax = '';
    momentumMin = '';
    changeMin = '';
    activePreset = '';
  }

  function applyPreset(preset: (typeof presets)[number]) {
    resetFilters();
    activePreset = preset.label;
    marketCapMin = preset.marketCapMin?.toString() ?? '';
    perMax = preset.perMax?.toString() ?? '';
    pbrMax = preset.pbrMax?.toString() ?? '';
    roeMin = preset.roeMin?.toString() ?? '';
    debtRatioMax = preset.debtRatioMax?.toString() ?? '';
    dividendMin = preset.dividendMin?.toString() ?? '';
    momentumMin = preset.momentumMin?.toString() ?? '';
    changeMin = preset.changeMin?.toString() ?? '';
  }

  function formatKrw(value: number) {
    return `${new Intl.NumberFormat('ko-KR').format(value)}원`;
  }

</script>

<svelte:head>
  <title>검색기 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">종목 검색기</p>
    <h1>시장, 밸류에이션, 재무, 기술 조건으로 후보를 좁힙니다.</h1>
  </div>
  <button type="button" class="secondary" onclick={resetFilters}>초기화</button>
</header>

<section class="screener-layout">
  <aside class="panel filter-sidebar" aria-label="스크리너 필터">
    <div class="panel-heading inline">
      <div>
        <span>필터</span>
        <strong>적용 {appliedFilterCount}개</strong>
      </div>
      <span class="status-pill ready">{filteredRows.length}개</span>
    </div>

    <div class="category-tabs" aria-label="필터 분류">
      {#each categories as category}
        <button
          type="button"
          class:active={activeCategory === category}
          onclick={() => (activeCategory = category)}
        >
          {category}
        </button>
      {/each}
    </div>

    <div class="filter-group">
      <label>
        <span>종목</span>
        <input bind:value={query} placeholder="종목명, 코드, 업종" type="search" />
      </label>

      <label>
        <span>거래소</span>
        <select bind:value={exchange}>
          <option value="all">전체</option>
          <option value="KOSPI">KOSPI</option>
          <option value="KOSDAQ">KOSDAQ</option>
        </select>
      </label>

      <label>
        <span>섹터</span>
        <select bind:value={sector}>
          <option value="all">전체</option>
          {#each sectors as sectorOption}
            <option value={sectorOption}>{sectorOption}</option>
          {/each}
        </select>
      </label>
    </div>

    <div class="filter-group">
      <strong>가격</strong>
      <div class="range-row">
        <label>
          <span>시가총액 최소(조)</span>
          <input bind:value={marketCapMin} min="0" step="1" type="number" />
        </label>
        <label>
          <span>시가총액 최대(조)</span>
          <input bind:value={marketCapMax} min="0" step="1" type="number" />
        </label>
      </div>
      <div class="range-row">
        <label>
          <span>가격 최소</span>
          <input bind:value={priceMin} min="0" step="100" type="number" />
        </label>
        <label>
          <span>가격 최대</span>
          <input bind:value={priceMax} min="0" step="100" type="number" />
        </label>
      </div>
    </div>

    <div class="filter-group">
      <strong>밸류에이션</strong>
      <div class="range-row">
        <label>
          <span>PER 최대</span>
          <input bind:value={perMax} min="0" step="0.1" type="number" />
        </label>
        <label>
          <span>PBR 최대</span>
          <input bind:value={pbrMax} min="0" step="0.1" type="number" />
        </label>
      </div>
    </div>

    <div class="filter-group">
      <strong>재무/배당/기술</strong>
      <div class="range-row">
        <label>
          <span>배당수익률 최소(%)</span>
          <input bind:value={dividendMin} min="0" step="0.1" type="number" />
        </label>
        <label>
          <span>ROE 최소(%)</span>
          <input bind:value={roeMin} step="0.1" type="number" />
        </label>
      </div>
      <div class="range-row">
        <label>
          <span>부채비율 최대(%)</span>
          <input bind:value={debtRatioMax} min="0" step="1" type="number" />
        </label>
        <label>
          <span>모멘텀 최소</span>
          <input bind:value={momentumMin} max="100" min="0" step="1" type="number" />
        </label>
      </div>
      <label>
        <span>일일 변동률 최소(%)</span>
        <input bind:value={changeMin} step="0.1" type="number" />
      </label>
    </div>
  </aside>

  <section class="screener-main">
    <section class="panel">
      <div class="panel-heading inline">
        <div>
          <span>인기 종목검색기</span>
          <strong>{activePreset || '프리셋 선택'}</strong>
        </div>
        <button type="button" class="secondary disabled" disabled>저장 예정</button>
      </div>
      <div class="preset-grid">
        {#each presets as preset}
          <button
            type="button"
            class:active={activePreset === preset.label}
            onclick={() => applyPreset(preset)}
          >
            {preset.label}
          </button>
        {/each}
      </div>
      <code class="formula-box">{formulaPreview}</code>
    </section>

    <section class="panel">
      <div class="panel-heading inline">
        <div>
          <span>검색 결과</span>
          <strong>{filteredRows.length}개 종목</strong>
        </div>
        <span class="muted">KRW 기준</span>
      </div>
      <div class="table-wrap">
        <table class="wide-table">
          <thead>
            <tr>
              <th>종목</th>
              <th>거래소</th>
              <th>섹터</th>
              <th>시가총액</th>
              <th>가격</th>
              <th>등락</th>
              <th>PER</th>
              <th>PBR</th>
              <th>배당</th>
              <th>ROE</th>
              <th>부채</th>
              <th>모멘텀</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredRows as row}
              <tr>
                <td>
                  <strong>{row.name}</strong>
                  <span>{row.symbol} · {row.industry}</span>
                </td>
                <td>{row.exchange}</td>
                <td>{row.sector}</td>
                <td>{row.marketCap.toLocaleString('ko-KR')}조</td>
                <td>{formatKrw(row.price)}</td>
                <td class:tone-positive={row.changePct > 0} class:tone-caution={row.changePct < 0}>
                  <strong>{row.changePct}%</strong>
                </td>
                <td>{row.per}x</td>
                <td>{row.pbr}x</td>
                <td>{row.dividendYield}%</td>
                <td>{row.roe}%</td>
                <td>{row.debtRatio}%</td>
                <td>
                  <meter min="0" max="100" value={row.momentum}>{row.momentum}</meter>
                  <b>{row.momentum}</b>
                </td>
              </tr>
            {:else}
              <tr>
                <td colspan="12">
                  <div class="empty-state">현재 조건에 맞는 종목이 없습니다.</div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>
  </section>
</section>
