<script lang="ts">
  import { onMount } from 'svelte';
  import {
    createUserStrategy,
    deleteUserStrategy,
    fetchUserStrategies,
    searchScreener,
    type StrategyCandidateResult,
    type UserStrategy
  } from '$lib/api';

  type ScreenerRow = {
    symbol: string;
    name: string;
    exchange: string;
    sector: string;
    industry: string;
    marketCap: number;
    price: number;
    changePct: number;
    tradingValue: number;
    avgVolume20d: number;
    turnover: number;
    per: number;
    pbr: number;
    psr: number;
    evEbitda: number;
    fcfYield: number;
    dividendYield: number;
    payoutRatio: number;
    roe: number;
    roa: number;
    operatingMargin: number;
    netMargin: number;
    debtRatio: number;
    currentRatio: number;
    revenueGrowth: number;
    epsGrowth: number;
    operatingIncomeGrowth: number;
    beta: number;
    volatility20d: number;
    drawdown52w: number;
    momentum: number;
    rsi14: number;
    closeVsMa20: number;
    closeVsMa60: number;
    volumeSurge: number;
    fairValueUpside: number;
    foreignNetBuy5d: number;
    foreignNetBuy20d: number;
    institutionNetBuy5d: number;
    institutionNetBuy20d: number;
    pensionNetBuy20d: number;
    programNetBuy5d: number;
    consecutiveForeignBuyDays: number;
    shortSaleRatio: number;
    marginDebtChange5d: number;
    supplyScore: number;
  };

  type FilterChip = {
    key: string;
    label: string;
  };

  const fallbackRows: ScreenerRow[] = [
    {
      symbol: '005930',
      name: '삼성전자',
      exchange: 'KOSPI',
      sector: '기술',
      industry: '반도체',
      marketCap: 2247.7,
      price: 354000,
      changePct: -2.3,
      tradingValue: 18200,
      avgVolume20d: 1450,
      turnover: 0.8,
      per: 14.8,
      pbr: 1.4,
      psr: 2.1,
      evEbitda: 7.8,
      fcfYield: 3.2,
      dividendYield: 1.7,
      payoutRatio: 24,
      roe: 9.8,
      roa: 6.1,
      operatingMargin: 15.4,
      netMargin: 10.2,
      debtRatio: 34,
      currentRatio: 248,
      revenueGrowth: 8.4,
      epsGrowth: 21.2,
      operatingIncomeGrowth: 28.6,
      beta: 1.05,
      volatility20d: 24.5,
      drawdown52w: -11.8,
      momentum: 82,
      rsi14: 58,
      closeVsMa20: 4.8,
      closeVsMa60: 9.2,
      volumeSurge: 1.4,
      fairValueUpside: 21.8,
      foreignNetBuy5d: 1260,
      foreignNetBuy20d: 4380,
      institutionNetBuy5d: 820,
      institutionNetBuy20d: 2110,
      pensionNetBuy20d: 920,
      programNetBuy5d: 710,
      consecutiveForeignBuyDays: 4,
      shortSaleRatio: 3.1,
      marginDebtChange5d: -2.4,
      supplyScore: 86
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
      tradingValue: 15600,
      avgVolume20d: 980,
      turnover: 1.1,
      per: 18.3,
      pbr: 1.6,
      psr: 2.8,
      evEbitda: 8.6,
      fcfYield: 2.4,
      dividendYield: 0.6,
      payoutRatio: 12,
      roe: 12.2,
      roa: 7.4,
      operatingMargin: 18.1,
      netMargin: 11.7,
      debtRatio: 58,
      currentRatio: 176,
      revenueGrowth: 17.2,
      epsGrowth: 35.4,
      operatingIncomeGrowth: 44.1,
      beta: 1.22,
      volatility20d: 31.8,
      drawdown52w: -14.6,
      momentum: 78,
      rsi14: 63,
      closeVsMa20: 6.4,
      closeVsMa60: 12.8,
      volumeSurge: 1.8,
      fairValueUpside: 3.4,
      foreignNetBuy5d: 2480,
      foreignNetBuy20d: 5120,
      institutionNetBuy5d: 1120,
      institutionNetBuy20d: 2680,
      pensionNetBuy20d: 540,
      programNetBuy5d: 1320,
      consecutiveForeignBuyDays: 6,
      shortSaleRatio: 4.9,
      marginDebtChange5d: 1.8,
      supplyScore: 91
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
      tradingValue: 1450,
      avgVolume20d: 620,
      turnover: 0.9,
      per: 27.4,
      pbr: 1.1,
      psr: 1.5,
      evEbitda: 10.8,
      fcfYield: 1.7,
      dividendYield: 0.2,
      payoutRatio: 8,
      roe: 4.5,
      roa: 2.7,
      operatingMargin: 7.6,
      netMargin: 4.8,
      debtRatio: 71,
      currentRatio: 132,
      revenueGrowth: 3.1,
      epsGrowth: -7.2,
      operatingIncomeGrowth: -4.5,
      beta: 1.34,
      volatility20d: 38.2,
      drawdown52w: -28.8,
      momentum: 71,
      rsi14: 54,
      closeVsMa20: 2.1,
      closeVsMa60: -3.4,
      volumeSurge: 1.2,
      fairValueUpside: 12.1,
      foreignNetBuy5d: 180,
      foreignNetBuy20d: -420,
      institutionNetBuy5d: 260,
      institutionNetBuy20d: 310,
      pensionNetBuy20d: 90,
      programNetBuy5d: 120,
      consecutiveForeignBuyDays: 2,
      shortSaleRatio: 6.2,
      marginDebtChange5d: 4.8,
      supplyScore: 58
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
      tradingValue: 3740,
      avgVolume20d: 310,
      turnover: 0.7,
      per: 6.2,
      pbr: 0.8,
      psr: 0.5,
      evEbitda: 4.1,
      fcfYield: 7.8,
      dividendYield: 4.1,
      payoutRatio: 28,
      roe: 14.9,
      roa: 5.9,
      operatingMargin: 9.7,
      netMargin: 8.8,
      debtRatio: 128,
      currentRatio: 118,
      revenueGrowth: 6.8,
      epsGrowth: 12.7,
      operatingIncomeGrowth: 10.3,
      beta: 0.92,
      volatility20d: 22.1,
      drawdown52w: -9.6,
      momentum: 66,
      rsi14: 51,
      closeVsMa20: 1.8,
      closeVsMa60: 4.9,
      volumeSurge: 1.1,
      fairValueUpside: 14.2,
      foreignNetBuy5d: 710,
      foreignNetBuy20d: 1890,
      institutionNetBuy5d: 640,
      institutionNetBuy20d: 1520,
      pensionNetBuy20d: 480,
      programNetBuy5d: 350,
      consecutiveForeignBuyDays: 3,
      shortSaleRatio: 2.2,
      marginDebtChange5d: -1.1,
      supplyScore: 76
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
      tradingValue: 980,
      avgVolume20d: 270,
      turnover: 0.5,
      per: 21.6,
      pbr: 1.2,
      psr: 2.0,
      evEbitda: 9.7,
      fcfYield: 3.1,
      dividendYield: 0.5,
      payoutRatio: 14,
      roe: 7.3,
      roa: 4.4,
      operatingMargin: 12.5,
      netMargin: 8.9,
      debtRatio: 44,
      currentRatio: 211,
      revenueGrowth: 7.9,
      epsGrowth: 8.6,
      operatingIncomeGrowth: 9.4,
      beta: 1.08,
      volatility20d: 29.7,
      drawdown52w: -19.4,
      momentum: 63,
      rsi14: 47,
      closeVsMa20: -1.2,
      closeVsMa60: 1.4,
      volumeSurge: 0.9,
      fairValueUpside: 18.7,
      foreignNetBuy5d: -120,
      foreignNetBuy20d: 260,
      institutionNetBuy5d: 330,
      institutionNetBuy20d: 740,
      pensionNetBuy20d: 180,
      programNetBuy5d: -70,
      consecutiveForeignBuyDays: 0,
      shortSaleRatio: 5.4,
      marginDebtChange5d: 2.6,
      supplyScore: 49
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
      tradingValue: 2140,
      avgVolume20d: 420,
      turnover: 2.4,
      per: 38.5,
      pbr: 3.9,
      psr: 3.4,
      evEbitda: 18.2,
      fcfYield: -1.6,
      dividendYield: 0.0,
      payoutRatio: 0,
      roe: 6.1,
      roa: 3.0,
      operatingMargin: 5.9,
      netMargin: 3.7,
      debtRatio: 96,
      currentRatio: 104,
      revenueGrowth: 14.8,
      epsGrowth: -11.4,
      operatingIncomeGrowth: -8.6,
      beta: 1.71,
      volatility20d: 55.3,
      drawdown52w: -42.2,
      momentum: 74,
      rsi14: 68,
      closeVsMa20: 9.7,
      closeVsMa60: 6.2,
      volumeSurge: 2.3,
      fairValueUpside: -8.4,
      foreignNetBuy5d: 340,
      foreignNetBuy20d: -820,
      institutionNetBuy5d: 520,
      institutionNetBuy20d: 610,
      pensionNetBuy20d: 40,
      programNetBuy5d: 280,
      consecutiveForeignBuyDays: 1,
      shortSaleRatio: 8.7,
      marginDebtChange5d: 8.2,
      supplyScore: 64
    }
  ];

  const categories = [
    '인기 항목',
    '프로필',
    '가격/유동성',
    '밸류에이션',
    '수익성',
    '성장',
    '배당',
    '리스크',
    '기술적 분석',
    '수급'
  ];

  const presets = [
    { label: '대형 우량주', marketCapMin: 100, perMax: 20, debtRatioMax: 150, roeMin: 8 },
    { label: '저평가 후보', pbrMax: 1.2, perMax: 15, roeMin: 8, fcfYieldMin: 3 },
    { label: '모멘텀 후보', momentumMin: 70, changeMin: 0, volumeSurgeMin: 1.2 },
    { label: '수급 유입주', foreignNetBuy5dMin: 300, institutionNetBuy5dMin: 300, supplyScoreMin: 70 },
    { label: '배당 관심주', dividendMin: 2, payoutRatioMax: 60, debtRatioMax: 180 }
  ];

  let query = '';
  let exchange = 'all';
  let sector = 'all';
  let industry = '';
  let marketCapMin = '';
  let marketCapMax = '';
  let priceMin = '';
  let priceMax = '';
  let tradingValueMin = '';
  let avgVolume20dMin = '';
  let turnoverMin = '';
  let perMax = '';
  let pbrMax = '';
  let psrMax = '';
  let evEbitdaMax = '';
  let fcfYieldMin = '';
  let fairValueUpsideMin = '';
  let dividendMin = '';
  let payoutRatioMax = '';
  let roeMin = '';
  let roaMin = '';
  let operatingMarginMin = '';
  let netMarginMin = '';
  let debtRatioMax = '';
  let currentRatioMin = '';
  let revenueGrowthMin = '';
  let epsGrowthMin = '';
  let operatingIncomeGrowthMin = '';
  let betaMax = '';
  let volatility20dMax = '';
  let drawdown52wMax = '';
  let momentumMin = '';
  let changeMin = '';
  let rsiMin = '';
  let rsiMax = '';
  let closePosition = 'all';
  let volumeSurgeMin = '';
  let foreignNetBuy5dMin = '';
  let foreignNetBuy20dMin = '';
  let institutionNetBuy5dMin = '';
  let institutionNetBuy20dMin = '';
  let pensionNetBuy20dMin = '';
  let programNetBuy5dMin = '';
  let consecutiveForeignBuyDaysMin = '';
  let shortSaleRatioMax = '';
  let marginDebtChange5dMax = '';
  let supplyScoreMin = '';
  let activeCategory = categories[0];
  let activePreset = '';
  let strategyName = '';
  let strategySummary = '';
  let registeredStrategies: UserStrategy[] = [];
  let strategyPersistenceError = '';
  let strategySaving = false;
  let strategyModalOpen = false;
  let deletingStrategyCode = '';
  let activeFilterChips: FilterChip[] = [];
  let categoryCounts: Record<string, number> = {};
  let rows: ScreenerRow[] = [];
  let screenerLoading = true;
  let screenerError = '';
  let screenerSource = '실제 데이터 확인 중';
  let screenerReady = false;
  let lastScreenerFormula = '';
  let screenerSearchTimer: ReturnType<typeof setTimeout> | undefined;

  onMount(async () => {
    await loadRegisteredStrategies();
    screenerReady = true;
    await loadScreenerRows(formulaPreview);
  });

  $: sectors = Array.from(new Set(rows.map((row) => row.sector)));
  $: showPopularGroup = activeCategory === '인기 항목';
  $: showProfileGroup = activeCategory === '프로필';
  $: showLiquidityGroup = activeCategory === '가격/유동성';
  $: showValuationGroup = activeCategory === '밸류에이션';
  $: showProfitabilityGroup = activeCategory === '수익성';
  $: showGrowthRiskGroup = ['성장', '배당', '리스크'].includes(activeCategory);
  $: showTechnicalGroup = activeCategory === '기술적 분석';
  $: showSupplyGroup = activeCategory === '수급';
  $: filteredRows = rows.filter((row) => {
    const normalizedQuery = query.trim().toLowerCase();
    const normalizedIndustry = industry.trim().toLowerCase();
    const matchesQuery =
      !normalizedQuery ||
      [row.name, row.symbol, row.exchange, row.sector, row.industry]
        .join(' ')
        .toLowerCase()
        .includes(normalizedQuery);
    const matchesIndustry = !normalizedIndustry || row.industry.toLowerCase().includes(normalizedIndustry);

    return (
      matchesQuery &&
      matchesIndustry &&
      (exchange === 'all' || row.exchange === exchange) &&
      (sector === 'all' || row.sector === sector) &&
      passesMin(row.marketCap, marketCapMin) &&
      passesMax(row.marketCap, marketCapMax) &&
      passesMin(row.price, priceMin) &&
      passesMax(row.price, priceMax) &&
      passesMin(row.tradingValue, tradingValueMin) &&
      passesMin(row.avgVolume20d, avgVolume20dMin) &&
      passesMin(row.turnover, turnoverMin) &&
      passesMax(row.per, perMax) &&
      passesMax(row.pbr, pbrMax) &&
      passesMax(row.psr, psrMax) &&
      passesMax(row.evEbitda, evEbitdaMax) &&
      passesMin(row.fcfYield, fcfYieldMin) &&
      passesMin(row.fairValueUpside, fairValueUpsideMin) &&
      passesMin(row.dividendYield, dividendMin) &&
      passesMax(row.payoutRatio, payoutRatioMax) &&
      passesMin(row.roe, roeMin) &&
      passesMin(row.roa, roaMin) &&
      passesMin(row.operatingMargin, operatingMarginMin) &&
      passesMin(row.netMargin, netMarginMin) &&
      passesMax(row.debtRatio, debtRatioMax) &&
      passesMin(row.currentRatio, currentRatioMin) &&
      passesMin(row.revenueGrowth, revenueGrowthMin) &&
      passesMin(row.epsGrowth, epsGrowthMin) &&
      passesMin(row.operatingIncomeGrowth, operatingIncomeGrowthMin) &&
      passesMax(row.beta, betaMax) &&
      passesMax(row.volatility20d, volatility20dMax) &&
      passesDrawdown(row.drawdown52w, drawdown52wMax) &&
      passesMin(row.momentum, momentumMin) &&
      passesMin(row.changePct, changeMin) &&
      passesMin(row.rsi14, rsiMin) &&
      passesMax(row.rsi14, rsiMax) &&
      passesClosePosition(row) &&
      passesMin(row.volumeSurge, volumeSurgeMin) &&
      passesMin(row.foreignNetBuy5d, foreignNetBuy5dMin) &&
      passesMin(row.foreignNetBuy20d, foreignNetBuy20dMin) &&
      passesMin(row.institutionNetBuy5d, institutionNetBuy5dMin) &&
      passesMin(row.institutionNetBuy20d, institutionNetBuy20dMin) &&
      passesMin(row.pensionNetBuy20d, pensionNetBuy20dMin) &&
      passesMin(row.programNetBuy5d, programNetBuy5dMin) &&
      passesMin(row.consecutiveForeignBuyDays, consecutiveForeignBuyDaysMin) &&
      passesMax(row.shortSaleRatio, shortSaleRatioMax) &&
      passesMax(row.marginDebtChange5d, marginDebtChange5dMax) &&
      passesMin(row.supplyScore, supplyScoreMin)
    );
  });
  $: appliedFilterCount = [
    query,
    exchange !== 'all' ? exchange : '',
    sector !== 'all' ? sector : '',
    industry,
    marketCapMin,
    marketCapMax,
    priceMin,
    priceMax,
    tradingValueMin,
    avgVolume20dMin,
    turnoverMin,
    perMax,
    pbrMax,
    psrMax,
    evEbitdaMax,
    fcfYieldMin,
    fairValueUpsideMin,
    dividendMin,
    payoutRatioMax,
    roeMin,
    roaMin,
    operatingMarginMin,
    netMarginMin,
    debtRatioMax,
    currentRatioMin,
    revenueGrowthMin,
    epsGrowthMin,
    operatingIncomeGrowthMin,
    betaMax,
    volatility20dMax,
    drawdown52wMax,
    momentumMin,
    changeMin,
    rsiMin,
    rsiMax,
    closePosition !== 'all' ? closePosition : '',
    volumeSurgeMin,
    foreignNetBuy5dMin,
    foreignNetBuy20dMin,
    institutionNetBuy5dMin,
    institutionNetBuy20dMin,
    pensionNetBuy20dMin,
    programNetBuy5dMin,
    consecutiveForeignBuyDaysMin,
    shortSaleRatioMax,
    marginDebtChange5dMax,
    supplyScoreMin
  ].filter(Boolean).length;
  $: formulaPreview =
    [
      query ? `keyword contains "${query}"` : '',
      exchange !== 'all' ? `exchange == "${exchange}"` : '',
      sector !== 'all' ? `sector == "${sector}"` : '',
      industry ? `industry contains "${industry}"` : '',
      marketCapMin ? `market_cap_trillion >= ${marketCapMin}` : '',
      marketCapMax ? `market_cap_trillion <= ${marketCapMax}` : '',
      priceMin ? `close >= ${priceMin}` : '',
      priceMax ? `close <= ${priceMax}` : '',
      tradingValueMin ? `trading_value_억원 >= ${tradingValueMin}` : '',
      avgVolume20dMin ? `avg_volume_20d_만주 >= ${avgVolume20dMin}` : '',
      turnoverMin ? `turnover_pct >= ${turnoverMin}` : '',
      perMax ? `per <= ${perMax}` : '',
      pbrMax ? `pbr <= ${pbrMax}` : '',
      psrMax ? `psr <= ${psrMax}` : '',
      evEbitdaMax ? `ev_ebitda <= ${evEbitdaMax}` : '',
      fcfYieldMin ? `fcf_yield >= ${fcfYieldMin}` : '',
      fairValueUpsideMin ? `fair_value_upside >= ${fairValueUpsideMin}` : '',
      dividendMin ? `dividend_yield >= ${dividendMin}` : '',
      payoutRatioMax ? `payout_ratio <= ${payoutRatioMax}` : '',
      roeMin ? `roe >= ${roeMin}` : '',
      roaMin ? `roa >= ${roaMin}` : '',
      operatingMarginMin ? `operating_margin >= ${operatingMarginMin}` : '',
      netMarginMin ? `net_margin >= ${netMarginMin}` : '',
      debtRatioMax ? `debt_ratio <= ${debtRatioMax}` : '',
      currentRatioMin ? `current_ratio >= ${currentRatioMin}` : '',
      revenueGrowthMin ? `revenue_growth >= ${revenueGrowthMin}` : '',
      epsGrowthMin ? `eps_growth >= ${epsGrowthMin}` : '',
      operatingIncomeGrowthMin ? `operating_income_growth >= ${operatingIncomeGrowthMin}` : '',
      betaMax ? `beta <= ${betaMax}` : '',
      volatility20dMax ? `volatility_20d <= ${volatility20dMax}` : '',
      drawdown52wMax ? `drawdown_52w >= -${drawdown52wMax}` : '',
      momentumMin ? `momentum_score >= ${momentumMin}` : '',
      changeMin ? `daily_change_pct >= ${changeMin}` : '',
      rsiMin ? `rsi14 >= ${rsiMin}` : '',
      rsiMax ? `rsi14 <= ${rsiMax}` : '',
      closePosition !== 'all' ? closePositionExpression(closePosition) : '',
      volumeSurgeMin ? `volume_surge >= ${volumeSurgeMin}` : '',
      foreignNetBuy5dMin ? `foreign_net_buy_5d_억원 >= ${foreignNetBuy5dMin}` : '',
      foreignNetBuy20dMin ? `foreign_net_buy_20d_억원 >= ${foreignNetBuy20dMin}` : '',
      institutionNetBuy5dMin ? `institution_net_buy_5d_억원 >= ${institutionNetBuy5dMin}` : '',
      institutionNetBuy20dMin ? `institution_net_buy_20d_억원 >= ${institutionNetBuy20dMin}` : '',
      pensionNetBuy20dMin ? `pension_net_buy_20d_억원 >= ${pensionNetBuy20dMin}` : '',
      programNetBuy5dMin ? `program_net_buy_5d_억원 >= ${programNetBuy5dMin}` : '',
      consecutiveForeignBuyDaysMin ? `foreign_buy_days >= ${consecutiveForeignBuyDaysMin}` : '',
      shortSaleRatioMax ? `short_sale_ratio <= ${shortSaleRatioMax}` : '',
      marginDebtChange5dMax ? `margin_debt_change_5d <= ${marginDebtChange5dMax}` : '',
      supplyScoreMin ? `supply_score >= ${supplyScoreMin}` : ''
    ]
      .filter(Boolean)
      .join(' AND ') || '필터를 선택하면 조건식 초안이 표시됩니다.';
  $: {
    query;
    exchange;
    sector;
    industry;
    marketCapMin;
    marketCapMax;
    priceMin;
    priceMax;
    tradingValueMin;
    avgVolume20dMin;
    turnoverMin;
    perMax;
    pbrMax;
    psrMax;
    evEbitdaMax;
    fcfYieldMin;
    fairValueUpsideMin;
    dividendMin;
    payoutRatioMax;
    roeMin;
    roaMin;
    operatingMarginMin;
    netMarginMin;
    debtRatioMax;
    currentRatioMin;
    revenueGrowthMin;
    epsGrowthMin;
    operatingIncomeGrowthMin;
    betaMax;
    volatility20dMax;
    drawdown52wMax;
    momentumMin;
    changeMin;
    rsiMin;
    rsiMax;
    closePosition;
    volumeSurgeMin;
    foreignNetBuy5dMin;
    foreignNetBuy20dMin;
    institutionNetBuy5dMin;
    institutionNetBuy20dMin;
    pensionNetBuy20dMin;
    programNetBuy5dMin;
    consecutiveForeignBuyDaysMin;
    shortSaleRatioMax;
    marginDebtChange5dMax;
    supplyScoreMin;
    activeFilterChips = buildFilterChips();
    categoryCounts = buildCategoryCounts();
  }
  $: if (screenerReady && formulaPreview !== lastScreenerFormula) {
    scheduleScreenerSearch(formulaPreview);
  }

  function countSelected(values: Array<string | boolean>) {
    return values.filter(Boolean).length;
  }

  function buildCategoryCounts() {
    return {
      '인기 항목': countSelected([
        marketCapMin,
        perMax,
        pbrMax,
        roeMin,
        momentumMin,
        volumeSurgeMin,
        foreignNetBuy5dMin,
        institutionNetBuy5dMin,
        supplyScoreMin
      ]),
      프로필: countSelected([query, exchange !== 'all', sector !== 'all', industry]),
      '가격/유동성': countSelected([
        marketCapMin,
        marketCapMax,
        priceMin,
        priceMax,
        tradingValueMin,
        avgVolume20dMin,
        turnoverMin
      ]),
      밸류에이션: countSelected([perMax, pbrMax, psrMax, evEbitdaMax, fcfYieldMin, fairValueUpsideMin]),
      수익성: countSelected([roeMin, roaMin, operatingMarginMin, netMarginMin, debtRatioMax, currentRatioMin]),
      성장: countSelected([revenueGrowthMin, epsGrowthMin, operatingIncomeGrowthMin]),
      배당: countSelected([dividendMin, payoutRatioMax]),
      리스크: countSelected([betaMax, volatility20dMax, drawdown52wMax]),
      '기술적 분석': countSelected([
        momentumMin,
        changeMin,
        rsiMin,
        rsiMax,
        closePosition !== 'all',
        volumeSurgeMin
      ]),
      수급: countSelected([
        foreignNetBuy5dMin,
        foreignNetBuy20dMin,
        institutionNetBuy5dMin,
        institutionNetBuy20dMin,
        pensionNetBuy20dMin,
        programNetBuy5dMin,
        consecutiveForeignBuyDaysMin,
        shortSaleRatioMax,
        marginDebtChange5dMax,
        supplyScoreMin
      ])
    };
  }

  function buildFilterChips(): FilterChip[] {
    return [
      query ? { key: 'query', label: `종목 ${query}` } : null,
      exchange !== 'all' ? { key: 'exchange', label: `거래소 ${exchange}` } : null,
      sector !== 'all' ? { key: 'sector', label: `섹터 ${sector}` } : null,
      industry ? { key: 'industry', label: `산업 ${industry}` } : null,
      marketCapMin ? { key: 'marketCapMin', label: `시총 ${marketCapMin}조 이상` } : null,
      marketCapMax ? { key: 'marketCapMax', label: `시총 ${marketCapMax}조 이하` } : null,
      priceMin ? { key: 'priceMin', label: `가격 ${Number(priceMin).toLocaleString('ko-KR')}원 이상` } : null,
      priceMax ? { key: 'priceMax', label: `가격 ${Number(priceMax).toLocaleString('ko-KR')}원 이하` } : null,
      tradingValueMin ? { key: 'tradingValueMin', label: `거래대금 ${tradingValueMin}억 이상` } : null,
      avgVolume20dMin ? { key: 'avgVolume20dMin', label: `20일 거래량 ${avgVolume20dMin}만주 이상` } : null,
      turnoverMin ? { key: 'turnoverMin', label: `회전율 ${turnoverMin}% 이상` } : null,
      perMax ? { key: 'perMax', label: `PER ${perMax} 이하` } : null,
      pbrMax ? { key: 'pbrMax', label: `PBR ${pbrMax} 이하` } : null,
      psrMax ? { key: 'psrMax', label: `PSR ${psrMax} 이하` } : null,
      evEbitdaMax ? { key: 'evEbitdaMax', label: `EV/EBITDA ${evEbitdaMax} 이하` } : null,
      fcfYieldMin ? { key: 'fcfYieldMin', label: `FCF ${fcfYieldMin}% 이상` } : null,
      fairValueUpsideMin ? { key: 'fairValueUpsideMin', label: `상승여력 ${fairValueUpsideMin}% 이상` } : null,
      dividendMin ? { key: 'dividendMin', label: `배당 ${dividendMin}% 이상` } : null,
      payoutRatioMax ? { key: 'payoutRatioMax', label: `배당성향 ${payoutRatioMax}% 이하` } : null,
      roeMin ? { key: 'roeMin', label: `ROE ${roeMin}% 이상` } : null,
      roaMin ? { key: 'roaMin', label: `ROA ${roaMin}% 이상` } : null,
      operatingMarginMin ? { key: 'operatingMarginMin', label: `영업이익률 ${operatingMarginMin}% 이상` } : null,
      netMarginMin ? { key: 'netMarginMin', label: `순이익률 ${netMarginMin}% 이상` } : null,
      debtRatioMax ? { key: 'debtRatioMax', label: `부채비율 ${debtRatioMax}% 이하` } : null,
      currentRatioMin ? { key: 'currentRatioMin', label: `유동비율 ${currentRatioMin}% 이상` } : null,
      revenueGrowthMin ? { key: 'revenueGrowthMin', label: `매출성장 ${revenueGrowthMin}% 이상` } : null,
      epsGrowthMin ? { key: 'epsGrowthMin', label: `EPS성장 ${epsGrowthMin}% 이상` } : null,
      operatingIncomeGrowthMin
        ? { key: 'operatingIncomeGrowthMin', label: `영업익성장 ${operatingIncomeGrowthMin}% 이상` }
        : null,
      betaMax ? { key: 'betaMax', label: `베타 ${betaMax} 이하` } : null,
      volatility20dMax ? { key: 'volatility20dMax', label: `변동성 ${volatility20dMax}% 이하` } : null,
      drawdown52wMax ? { key: 'drawdown52wMax', label: `52주 낙폭 ${drawdown52wMax}% 이내` } : null,
      momentumMin ? { key: 'momentumMin', label: `모멘텀 ${momentumMin} 이상` } : null,
      changeMin ? { key: 'changeMin', label: `등락 ${changeMin}% 이상` } : null,
      rsiMin ? { key: 'rsiMin', label: `RSI ${rsiMin} 이상` } : null,
      rsiMax ? { key: 'rsiMax', label: `RSI ${rsiMax} 이하` } : null,
      closePosition !== 'all' ? { key: 'closePosition', label: closePositionLabel(closePosition) } : null,
      volumeSurgeMin ? { key: 'volumeSurgeMin', label: `거래량 ${volumeSurgeMin}배 이상` } : null,
      foreignNetBuy5dMin ? { key: 'foreignNetBuy5dMin', label: `외국인 5일 ${foreignNetBuy5dMin}억 이상` } : null,
      foreignNetBuy20dMin ? { key: 'foreignNetBuy20dMin', label: `외국인 20일 ${foreignNetBuy20dMin}억 이상` } : null,
      institutionNetBuy5dMin
        ? { key: 'institutionNetBuy5dMin', label: `기관 5일 ${institutionNetBuy5dMin}억 이상` }
        : null,
      institutionNetBuy20dMin
        ? { key: 'institutionNetBuy20dMin', label: `기관 20일 ${institutionNetBuy20dMin}억 이상` }
        : null,
      pensionNetBuy20dMin ? { key: 'pensionNetBuy20dMin', label: `연기금 20일 ${pensionNetBuy20dMin}억 이상` } : null,
      programNetBuy5dMin ? { key: 'programNetBuy5dMin', label: `프로그램 5일 ${programNetBuy5dMin}억 이상` } : null,
      consecutiveForeignBuyDaysMin
        ? { key: 'consecutiveForeignBuyDaysMin', label: `외국인 ${consecutiveForeignBuyDaysMin}일 연속` }
        : null,
      shortSaleRatioMax ? { key: 'shortSaleRatioMax', label: `공매도 ${shortSaleRatioMax}% 이하` } : null,
      marginDebtChange5dMax ? { key: 'marginDebtChange5dMax', label: `신용증가 ${marginDebtChange5dMax}% 이하` } : null,
      supplyScoreMin ? { key: 'supplyScoreMin', label: `수급점수 ${supplyScoreMin} 이상` } : null
    ].filter((chip): chip is FilterChip => Boolean(chip));
  }

  function passesMin(value: number, filterValue: string) {
    return !filterValue || value >= Number(filterValue);
  }

  function passesMax(value: number, filterValue: string) {
    return !filterValue || value <= Number(filterValue);
  }

  function passesDrawdown(value: number, filterValue: string) {
    return !filterValue || value >= -Math.abs(Number(filterValue));
  }

  function passesClosePosition(row: ScreenerRow) {
    if (closePosition === 'above-ma20') return row.closeVsMa20 > 0;
    if (closePosition === 'above-ma60') return row.closeVsMa60 > 0;
    if (closePosition === 'above-ma20-ma60') return row.closeVsMa20 > 0 && row.closeVsMa60 > 0;
    if (closePosition === 'pullback-ma20') return row.closeVsMa20 >= -3 && row.closeVsMa20 <= 3;
    return true;
  }

  function closePositionExpression(value: string) {
    if (value === 'above-ma20') return 'close > ma20';
    if (value === 'above-ma60') return 'close > ma60';
    if (value === 'above-ma20-ma60') return 'close > ma20 AND close > ma60';
    if (value === 'pullback-ma20') return 'abs(close_vs_ma20_pct) <= 3';
    return '';
  }

  function closePositionLabel(value: string) {
    if (value === 'above-ma20') return '20일선 위';
    if (value === 'above-ma60') return '60일선 위';
    if (value === 'above-ma20-ma60') return '20/60일선 위';
    if (value === 'pullback-ma20') return '20일선 눌림';
    return '';
  }

  function resetFilters() {
    query = '';
    exchange = 'all';
    sector = 'all';
    industry = '';
    marketCapMin = '';
    marketCapMax = '';
    priceMin = '';
    priceMax = '';
    tradingValueMin = '';
    avgVolume20dMin = '';
    turnoverMin = '';
    perMax = '';
    pbrMax = '';
    psrMax = '';
    evEbitdaMax = '';
    fcfYieldMin = '';
    fairValueUpsideMin = '';
    dividendMin = '';
    payoutRatioMax = '';
    roeMin = '';
    roaMin = '';
    operatingMarginMin = '';
    netMarginMin = '';
    debtRatioMax = '';
    currentRatioMin = '';
    revenueGrowthMin = '';
    epsGrowthMin = '';
    operatingIncomeGrowthMin = '';
    betaMax = '';
    volatility20dMax = '';
    drawdown52wMax = '';
    momentumMin = '';
    changeMin = '';
    rsiMin = '';
    rsiMax = '';
    closePosition = 'all';
    volumeSurgeMin = '';
    foreignNetBuy5dMin = '';
    foreignNetBuy20dMin = '';
    institutionNetBuy5dMin = '';
    institutionNetBuy20dMin = '';
    pensionNetBuy20dMin = '';
    programNetBuy5dMin = '';
    consecutiveForeignBuyDaysMin = '';
    shortSaleRatioMax = '';
    marginDebtChange5dMax = '';
    supplyScoreMin = '';
    activePreset = '';
  }

  function applyPreset(preset: (typeof presets)[number]) {
    activePreset = preset.label;
    marketCapMin = preset.marketCapMin?.toString() ?? marketCapMin;
    perMax = preset.perMax?.toString() ?? perMax;
    pbrMax = preset.pbrMax?.toString() ?? pbrMax;
    roeMin = preset.roeMin?.toString() ?? roeMin;
    debtRatioMax = preset.debtRatioMax?.toString() ?? debtRatioMax;
    dividendMin = preset.dividendMin?.toString() ?? dividendMin;
    payoutRatioMax = preset.payoutRatioMax?.toString() ?? payoutRatioMax;
    momentumMin = preset.momentumMin?.toString() ?? momentumMin;
    changeMin = preset.changeMin?.toString() ?? changeMin;
    volumeSurgeMin = preset.volumeSurgeMin?.toString() ?? volumeSurgeMin;
    fcfYieldMin = preset.fcfYieldMin?.toString() ?? fcfYieldMin;
    foreignNetBuy5dMin = preset.foreignNetBuy5dMin?.toString() ?? foreignNetBuy5dMin;
    institutionNetBuy5dMin = preset.institutionNetBuy5dMin?.toString() ?? institutionNetBuy5dMin;
    supplyScoreMin = preset.supplyScoreMin?.toString() ?? supplyScoreMin;
  }

  function clearFilter(key: string) {
    if (key === 'query') query = '';
    if (key === 'exchange') exchange = 'all';
    if (key === 'sector') sector = 'all';
    if (key === 'industry') industry = '';
    if (key === 'marketCapMin') marketCapMin = '';
    if (key === 'marketCapMax') marketCapMax = '';
    if (key === 'priceMin') priceMin = '';
    if (key === 'priceMax') priceMax = '';
    if (key === 'tradingValueMin') tradingValueMin = '';
    if (key === 'avgVolume20dMin') avgVolume20dMin = '';
    if (key === 'turnoverMin') turnoverMin = '';
    if (key === 'perMax') perMax = '';
    if (key === 'pbrMax') pbrMax = '';
    if (key === 'psrMax') psrMax = '';
    if (key === 'evEbitdaMax') evEbitdaMax = '';
    if (key === 'fcfYieldMin') fcfYieldMin = '';
    if (key === 'fairValueUpsideMin') fairValueUpsideMin = '';
    if (key === 'dividendMin') dividendMin = '';
    if (key === 'payoutRatioMax') payoutRatioMax = '';
    if (key === 'roeMin') roeMin = '';
    if (key === 'roaMin') roaMin = '';
    if (key === 'operatingMarginMin') operatingMarginMin = '';
    if (key === 'netMarginMin') netMarginMin = '';
    if (key === 'debtRatioMax') debtRatioMax = '';
    if (key === 'currentRatioMin') currentRatioMin = '';
    if (key === 'revenueGrowthMin') revenueGrowthMin = '';
    if (key === 'epsGrowthMin') epsGrowthMin = '';
    if (key === 'operatingIncomeGrowthMin') operatingIncomeGrowthMin = '';
    if (key === 'betaMax') betaMax = '';
    if (key === 'volatility20dMax') volatility20dMax = '';
    if (key === 'drawdown52wMax') drawdown52wMax = '';
    if (key === 'momentumMin') momentumMin = '';
    if (key === 'changeMin') changeMin = '';
    if (key === 'rsiMin') rsiMin = '';
    if (key === 'rsiMax') rsiMax = '';
    if (key === 'closePosition') closePosition = 'all';
    if (key === 'volumeSurgeMin') volumeSurgeMin = '';
    if (key === 'foreignNetBuy5dMin') foreignNetBuy5dMin = '';
    if (key === 'foreignNetBuy20dMin') foreignNetBuy20dMin = '';
    if (key === 'institutionNetBuy5dMin') institutionNetBuy5dMin = '';
    if (key === 'institutionNetBuy20dMin') institutionNetBuy20dMin = '';
    if (key === 'pensionNetBuy20dMin') pensionNetBuy20dMin = '';
    if (key === 'programNetBuy5dMin') programNetBuy5dMin = '';
    if (key === 'consecutiveForeignBuyDaysMin') consecutiveForeignBuyDaysMin = '';
    if (key === 'shortSaleRatioMax') shortSaleRatioMax = '';
    if (key === 'marginDebtChange5dMax') marginDebtChange5dMax = '';
    if (key === 'supplyScoreMin') supplyScoreMin = '';
  }

  function scheduleScreenerSearch(formula: string) {
    if (screenerSearchTimer) {
      clearTimeout(screenerSearchTimer);
    }
    screenerSearchTimer = setTimeout(() => {
      void loadScreenerRows(formula);
    }, 350);
  }

  async function loadScreenerRows(formula: string) {
    lastScreenerFormula = formula;
    screenerLoading = true;
    screenerError = '';

    try {
      const response = await searchScreener({
        strategy_code: 'relative-momentum-swing',
        formula,
        limit: 100
      });
      rows = response.candidates.map(toScreenerRow);
      screenerSource = candidateSourceLabel(response.source);
    } catch (err) {
      rows = fallbackRows;
      screenerSource = '샘플 후보군';
      screenerError = err instanceof Error ? err.message : '검색기 데이터를 불러오지 못했습니다.';
    } finally {
      screenerLoading = false;
    }
  }

  function toScreenerRow(candidate: StrategyCandidateResult): ScreenerRow {
    const fallback = fallbackRows.find((row) => row.symbol === candidate.symbol) ?? fallbackRows[0];

    return {
      ...fallback,
      symbol: candidate.symbol,
      name: candidate.name,
      exchange: candidate.exchange,
      sector: candidate.sector,
      industry: candidate.industry,
      marketCap: candidate.market_cap,
      price: candidate.price,
      changePct: candidate.change_pct,
      per: candidate.per,
      pbr: candidate.pbr,
      roe: candidate.roe,
      revenueGrowth: candidate.revenue_growth,
      foreignNetBuy5d: candidate.foreign_net_buy_5d,
      foreignNetBuy20d: candidate.foreign_net_buy_20d,
      institutionNetBuy5d: candidate.institution_net_buy_5d,
      institutionNetBuy20d: candidate.institution_net_buy_20d,
      pensionNetBuy20d: candidate.pension_net_buy_20d,
      programNetBuy5d: candidate.program_net_buy_5d,
      consecutiveForeignBuyDays: candidate.consecutive_foreign_buy_days,
      supplyScore: candidate.supply_score,
      shortSaleRatio: candidate.short_sale_ratio,
      marginDebtChange5d: candidate.margin_debt_change_5d,
      momentum: candidate.momentum,
      tradingValue: candidate.trading_value_krw_100m,
      avgVolume20d: candidate.avg_volume_20d_10k,
      turnover: candidate.turnover_pct,
      psr: candidate.psr,
      evEbitda: candidate.ev_ebitda,
      fcfYield: candidate.fcf_yield,
      dividendYield: candidate.dividend_yield,
      payoutRatio: candidate.payout_ratio,
      roa: candidate.roa,
      operatingMargin: candidate.operating_margin,
      netMargin: candidate.net_margin,
      debtRatio: candidate.debt_ratio,
      currentRatio: candidate.current_ratio,
      epsGrowth: candidate.eps_growth,
      operatingIncomeGrowth: candidate.operating_income_growth,
      beta: candidate.beta,
      volatility20d: candidate.volatility_20d,
      drawdown52w: candidate.drawdown_52w,
      rsi14: candidate.rsi14,
      closeVsMa20: candidate.close_vs_ma20_pct,
      closeVsMa60: candidate.close_vs_ma60_pct,
      volumeSurge: candidate.volume_surge,
      fairValueUpside: candidate.fair_value_upside
    };
  }

  function candidateSourceLabel(source: string) {
    if (source.startsWith('daily-price-candidates:')) {
      const provider = source
        .replace('daily-price-candidates:', '')
        .replace(':filtered', '')
        .replace(':screener-filtered', '');
      return `실제 일봉 기반 · ${provider}`;
    }
    if (source.includes('sample')) return '샘플 후보군';
    return source || '출처 확인 중';
  }

  async function loadRegisteredStrategies() {
    try {
      registeredStrategies = await fetchUserStrategies();
      strategyPersistenceError = '';
    } catch (err) {
      strategyPersistenceError = err instanceof Error ? err.message : '사용자 전략을 불러오지 못했습니다.';
    }
  }

  function openStrategyModal() {
    strategyModalOpen = true;
    strategyPersistenceError = '';
  }

  function closeStrategyModal() {
    strategyModalOpen = false;
  }

  async function registerStrategy() {
    const name = strategyName.trim() || `검색기 전략 ${registeredStrategies.length + 1}`;
    const summary = strategySummary.trim() || '검색기에서 저장한 조건 기반 전략입니다.';
    strategySaving = true;
    strategyPersistenceError = '';

    try {
      const created = await createUserStrategy({
        name,
        summary,
        formula: formulaPreview,
        result_count: filteredRows.length
      });

      registeredStrategies = [created, ...registeredStrategies];
      strategyName = '';
      strategySummary = '';
      strategyModalOpen = false;
    } catch (err) {
      strategyPersistenceError = err instanceof Error ? err.message : '사용자 전략을 저장하지 못했습니다.';
    } finally {
      strategySaving = false;
    }
  }

  async function removeRegisteredStrategy(strategyCode: string) {
    deletingStrategyCode = strategyCode;
    strategyPersistenceError = '';

    try {
      await deleteUserStrategy(strategyCode);
      registeredStrategies = registeredStrategies.filter((strategy) => strategy.code !== strategyCode);
    } catch (err) {
      strategyPersistenceError = err instanceof Error ? err.message : '사용자 전략을 삭제하지 못했습니다.';
    } finally {
      deletingStrategyCode = '';
    }
  }

  function formatKrw(value: number) {
    return `${new Intl.NumberFormat('ko-KR').format(value)}원`;
  }

  function formatSigned(value: number) {
    return value > 0 ? `+${value}` : `${value}`;
  }

  function formatStrategyDate(value: string) {
    return new Date(value).toLocaleString('ko-KR');
  }
</script>

<svelte:head>
  <title>검색기 | QuantMate</title>
</svelte:head>

<header class="topbar">
  <div>
    <p class="eyebrow">종목 검색기</p>
    <h1>퀀트 조건과 수급 유입 조건으로 후보를 좁힙니다.</h1>
  </div>
  <div class="action-row">
    <button type="button" onclick={openStrategyModal}>전략 등록</button>
  </div>
</header>

<section class="screener-workbench">
  <section class="panel popular-screeners" aria-label="인기 종목검색기">
    <div class="preset-strip">
      <div class="panel-heading inline">
        <div>
          <span>인기 종목검색기</span>
          <strong>{activePreset || '프리셋 선택'}</strong>
        </div>
        <span class="muted">선택한 조건은 현재 필터에 누적됩니다.</span>
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
    </div>
  </section>

  <section class="panel screener-builder" aria-label="검색식 설정">
    <div class="panel-heading inline filter-panel-heading">
      <div>
        <span>필터</span>
        <strong>적용 {appliedFilterCount}개 조건</strong>
      </div>
      <div class="filter-heading-actions">
        <span class="muted">실제 일봉 기준, 일부 재무/수급 보조값 포함</span>
        <button type="button" class="secondary" onclick={resetFilters}>초기화</button>
      </div>
    </div>

    <div class="category-tabs" aria-label="필터 분류">
      {#each categories as category}
        <button
          type="button"
          class:active={activeCategory === category}
          onclick={() => (activeCategory = category)}
        >
          <span>{category}</span>
          {#if categoryCounts[category]}
            <b>{categoryCounts[category]}</b>
          {/if}
        </button>
      {/each}
    </div>

    <div class="active-filter-bar" aria-label="선택된 필터">
      <strong>선택된 필터</strong>
      {#if activeFilterChips.length}
        <div class="active-filter-list">
          {#each activeFilterChips as chip}
            <button type="button" class="active-filter-chip" onclick={() => clearFilter(chip.key)}>
              {chip.label}
              <span aria-hidden="true">×</span>
            </button>
          {/each}
        </div>
      {:else}
        <span class="muted">조건을 선택하면 이곳에 누적됩니다.</span>
      {/if}
    </div>

    <div class="filter-groups">
      {#if showProfileGroup}
        <div class="filter-group inline-filter">
          <strong>프로필</strong>
          <div class="filter-controls">
            <label class="compact-control wide-control">
              <span>종목</span>
              <input bind:value={query} placeholder="종목명, 코드, 업종" type="search" />
            </label>
            <label class="compact-control">
              <span>거래소</span>
              <select bind:value={exchange}>
                <option value="all">전체</option>
                <option value="KOSPI">KOSPI</option>
                <option value="KOSDAQ">KOSDAQ</option>
              </select>
            </label>
            <label class="compact-control">
              <span>섹터</span>
              <select bind:value={sector}>
                <option value="all">전체</option>
                {#each sectors as sectorOption}
                  <option value={sectorOption}>{sectorOption}</option>
                {/each}
              </select>
            </label>
            <label class="compact-control">
              <span>산업</span>
              <input bind:value={industry} placeholder="예: 반도체" type="search" />
            </label>
          </div>
        </div>
      {/if}

      {#if showPopularGroup}
        <div class="filter-group featured-filter inline-filter">
          <strong>주요 조건</strong>
          <div class="filter-controls">
            <label class="compact-control">
              <span>시가총액 최소(조)</span>
              <input bind:value={marketCapMin} min="0" step="1" type="number" />
            </label>
            <label class="compact-control">
              <span>PER 최대</span>
              <input bind:value={perMax} min="0" step="0.1" type="number" />
            </label>
            <label class="compact-control">
              <span>PBR 최대</span>
              <input bind:value={pbrMax} min="0" step="0.1" type="number" />
            </label>
            <label class="compact-control">
              <span>ROE 최소(%)</span>
              <input bind:value={roeMin} step="0.1" type="number" />
            </label>
            <label class="compact-control">
              <span>모멘텀 최소</span>
              <input bind:value={momentumMin} max="100" min="0" step="1" type="number" />
            </label>
            <label class="compact-control">
              <span>거래량 급증 배수 최소</span>
              <input bind:value={volumeSurgeMin} min="0" step="0.1" type="number" />
            </label>
            <label class="compact-control">
              <span>외국인 5일 순매수 최소(억)</span>
              <input bind:value={foreignNetBuy5dMin} step="10" type="number" />
            </label>
            <label class="compact-control">
              <span>기관 5일 순매수 최소(억)</span>
              <input bind:value={institutionNetBuy5dMin} step="10" type="number" />
            </label>
            <label class="compact-control">
              <span>수급 점수 최소</span>
              <input bind:value={supplyScoreMin} max="100" min="0" step="1" type="number" />
            </label>
          </div>
        </div>
      {/if}

      {#if showLiquidityGroup}
      <div class="filter-group inline-filter">
        <strong>가격/유동성</strong>
        <div class="filter-controls">
          <label class="compact-control">
            <span>시가총액 최소(조)</span>
            <input bind:value={marketCapMin} min="0" step="1" type="number" />
          </label>
          <label class="compact-control">
            <span>시가총액 최대(조)</span>
            <input bind:value={marketCapMax} min="0" step="1" type="number" />
          </label>
          <label class="compact-control">
            <span>가격 최소</span>
            <input bind:value={priceMin} min="0" step="100" type="number" />
          </label>
          <label class="compact-control">
            <span>가격 최대</span>
            <input bind:value={priceMax} min="0" step="100" type="number" />
          </label>
          <label class="compact-control">
            <span>거래대금 최소(억)</span>
            <input bind:value={tradingValueMin} min="0" step="100" type="number" />
          </label>
          <label class="compact-control">
            <span>20일 거래량 최소(만주)</span>
            <input bind:value={avgVolume20dMin} min="0" step="10" type="number" />
          </label>
          <label class="compact-control">
            <span>회전율 최소(%)</span>
            <input bind:value={turnoverMin} min="0" step="0.1" type="number" />
          </label>
        </div>
      </div>
      {/if}

      {#if showValuationGroup}
      <div class="filter-group inline-filter">
        <strong>밸류에이션</strong>
        <div class="filter-controls">
          <label class="compact-control">
            <span>PER 최대</span>
            <input bind:value={perMax} min="0" step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>PBR 최대</span>
            <input bind:value={pbrMax} min="0" step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>PSR 최대</span>
            <input bind:value={psrMax} min="0" step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>EV/EBITDA 최대</span>
            <input bind:value={evEbitdaMax} min="0" step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>FCF 수익률 최소(%)</span>
            <input bind:value={fcfYieldMin} step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>적정가치 상승여력 최소(%)</span>
            <input bind:value={fairValueUpsideMin} step="0.1" type="number" />
          </label>
        </div>
      </div>
      {/if}

      {#if showProfitabilityGroup}
      <div class="filter-group inline-filter">
        <strong>수익성/재무</strong>
        <div class="filter-controls">
          <label class="compact-control">
            <span>ROE 최소(%)</span>
            <input bind:value={roeMin} step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>ROA 최소(%)</span>
            <input bind:value={roaMin} step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>영업이익률 최소(%)</span>
            <input bind:value={operatingMarginMin} step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>순이익률 최소(%)</span>
            <input bind:value={netMarginMin} step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>부채비율 최대(%)</span>
            <input bind:value={debtRatioMax} min="0" step="1" type="number" />
          </label>
          <label class="compact-control">
            <span>유동비율 최소(%)</span>
            <input bind:value={currentRatioMin} min="0" step="1" type="number" />
          </label>
        </div>
      </div>
      {/if}

      {#if showGrowthRiskGroup}
      <div class="filter-group inline-filter">
        <strong>성장/배당/리스크</strong>
        <div class="filter-controls">
          <label class="compact-control">
            <span>매출 성장률 최소(%)</span>
            <input bind:value={revenueGrowthMin} step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>EPS 성장률 최소(%)</span>
            <input bind:value={epsGrowthMin} step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>영업이익 성장률 최소(%)</span>
            <input bind:value={operatingIncomeGrowthMin} step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>배당수익률 최소(%)</span>
            <input bind:value={dividendMin} min="0" step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>배당성향 최대(%)</span>
            <input bind:value={payoutRatioMax} min="0" step="1" type="number" />
          </label>
          <label class="compact-control">
            <span>베타 최대</span>
            <input bind:value={betaMax} min="0" step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>20일 변동성 최대(%)</span>
            <input bind:value={volatility20dMax} min="0" step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>52주 낙폭 최대(%)</span>
            <input bind:value={drawdown52wMax} min="0" step="0.1" type="number" />
          </label>
        </div>
      </div>
      {/if}

      {#if showTechnicalGroup}
      <div class="filter-group inline-filter">
        <strong>기술적 분석</strong>
        <div class="filter-controls">
          <label class="compact-control">
            <span>모멘텀 최소</span>
            <input bind:value={momentumMin} max="100" min="0" step="1" type="number" />
          </label>
          <label class="compact-control">
            <span>일일 변동률 최소(%)</span>
            <input bind:value={changeMin} step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>RSI 최소</span>
            <input bind:value={rsiMin} max="100" min="0" step="1" type="number" />
          </label>
          <label class="compact-control">
            <span>RSI 최대</span>
            <input bind:value={rsiMax} max="100" min="0" step="1" type="number" />
          </label>
          <label class="compact-control">
            <span>이동평균 위치</span>
            <select bind:value={closePosition}>
              <option value="all">전체</option>
              <option value="above-ma20">20일선 위</option>
              <option value="above-ma60">60일선 위</option>
              <option value="above-ma20-ma60">20/60일선 모두 위</option>
              <option value="pullback-ma20">20일선 근처 눌림</option>
            </select>
          </label>
          <label class="compact-control">
            <span>거래량 급증 배수 최소</span>
            <input bind:value={volumeSurgeMin} min="0" step="0.1" type="number" />
          </label>
        </div>
      </div>
      {/if}

      {#if showSupplyGroup}
      <div class="filter-group supply-filter inline-filter">
        <strong>수급</strong>
        <div class="filter-controls">
          <label class="compact-control">
            <span>외국인 5일 순매수 최소(억)</span>
            <input bind:value={foreignNetBuy5dMin} step="10" type="number" />
          </label>
          <label class="compact-control">
            <span>외국인 20일 순매수 최소(억)</span>
            <input bind:value={foreignNetBuy20dMin} step="10" type="number" />
          </label>
          <label class="compact-control">
            <span>기관 5일 순매수 최소(억)</span>
            <input bind:value={institutionNetBuy5dMin} step="10" type="number" />
          </label>
          <label class="compact-control">
            <span>기관 20일 순매수 최소(억)</span>
            <input bind:value={institutionNetBuy20dMin} step="10" type="number" />
          </label>
          <label class="compact-control">
            <span>연기금 20일 순매수 최소(억)</span>
            <input bind:value={pensionNetBuy20dMin} step="10" type="number" />
          </label>
          <label class="compact-control">
            <span>프로그램 5일 순매수 최소(억)</span>
            <input bind:value={programNetBuy5dMin} step="10" type="number" />
          </label>
          <label class="compact-control">
            <span>외국인 연속 순매수일 최소</span>
            <input bind:value={consecutiveForeignBuyDaysMin} min="0" step="1" type="number" />
          </label>
          <label class="compact-control">
            <span>수급 점수 최소</span>
            <input bind:value={supplyScoreMin} max="100" min="0" step="1" type="number" />
          </label>
          <label class="compact-control">
            <span>공매도 비중 최대(%)</span>
            <input bind:value={shortSaleRatioMax} min="0" step="0.1" type="number" />
          </label>
          <label class="compact-control">
            <span>신용잔고 증가율 최대(%)</span>
            <input bind:value={marginDebtChange5dMax} step="0.1" type="number" />
          </label>
        </div>
      </div>
      {/if}
    </div>

  </section>

  <section class="panel screener-results">
    <div class="panel-heading inline">
      <div>
        <span>검색 결과</span>
        <strong>{filteredRows.length}개 종목</strong>
      </div>
      <span class="muted">{screenerLoading ? '검색기 데이터 갱신 중' : `${screenerSource} · KRW 기준`}</span>
    </div>
    {#if screenerError}
      <div class="empty-state error">{screenerError}</div>
    {/if}
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
            <th>ROE</th>
            <th>성장</th>
            <th>외국인 5일</th>
            <th>기관 5일</th>
            <th>수급 점수</th>
            <th>공매도</th>
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
              <td>{row.roe}%</td>
              <td>{row.revenueGrowth}%</td>
              <td class:tone-positive={row.foreignNetBuy5d > 0} class:tone-caution={row.foreignNetBuy5d < 0}>
                <strong>{formatSigned(row.foreignNetBuy5d)}억</strong>
              </td>
              <td class:tone-positive={row.institutionNetBuy5d > 0} class:tone-caution={row.institutionNetBuy5d < 0}>
                <strong>{formatSigned(row.institutionNetBuy5d)}억</strong>
              </td>
              <td>{row.supplyScore}</td>
              <td>{row.shortSaleRatio}%</td>
              <td>
                <meter min="0" max="100" value={row.momentum}>{row.momentum}</meter>
                <b>{row.momentum}</b>
              </td>
            </tr>
          {:else}
            <tr>
              <td colspan="15">
                <div class="empty-state">
                  {screenerLoading ? '검색기 데이터 갱신 중입니다.' : '현재 조건에 맞는 종목이 없습니다.'}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>
</section>

{#if strategyModalOpen}
  <div class="modal-backdrop" role="presentation"></div>
  <div
    class="modal-panel strategy-modal"
    role="dialog"
    aria-modal="true"
    aria-labelledby="strategy-modal-title"
  >
    <div class="modal-header">
      <div>
        <span>전략 등록</span>
        <h2 id="strategy-modal-title">현재 검색식 저장</h2>
        <p>현재 필터 결과 {filteredRows.length}개 후보를 전략으로 저장합니다.</p>
      </div>
      <button type="button" class="secondary icon-button" aria-label="닫기" onclick={closeStrategyModal}>×</button>
    </div>

    <div class="strategy-modal-form">
      <label>
        <span>전략명</span>
        <input bind:value={strategyName} placeholder="예: 외국인+기관 수급 유입주" />
      </label>
      <label>
        <span>소개</span>
        <textarea
          bind:value={strategySummary}
          rows="3"
          placeholder="예: 외국인과 기관 수급이 함께 들어오는 종목"
        ></textarea>
      </label>
    </div>

    {#if strategyPersistenceError}
      <div class="empty-state error">{strategyPersistenceError}</div>
    {/if}

    {#if registeredStrategies.length}
      <div class="registered-strategy-panel">
        <strong>저장된 검색기 전략</strong>
        <ul class="registered-strategies compact">
          {#each registeredStrategies as strategy}
            <li>
              <div>
                <strong>{strategy.name}</strong>
                <p>{strategy.summary}</p>
                <span>{formatStrategyDate(strategy.created_at)} · 후보 {strategy.result_count}개</span>
              </div>
              <button
                type="button"
                class="secondary"
                disabled={deletingStrategyCode === strategy.code}
                onclick={() => removeRegisteredStrategy(strategy.code)}
              >
                {deletingStrategyCode === strategy.code ? '삭제 중' : '삭제'}
              </button>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    <div class="modal-actions">
      <button type="button" class="secondary" onclick={closeStrategyModal}>취소</button>
      <button type="button" onclick={registerStrategy} disabled={strategySaving}>
        {strategySaving ? '저장 중' : '저장'}
      </button>
    </div>
  </div>
{/if}
