from __future__ import annotations

import json
import os
from datetime import date, datetime
from enum import StrEnum
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from quantmate_api.backtest_engine import build_sample_backtest
from quantmate_api.db import SessionLocal
from quantmate_api.market_data import (
    MarketDataProviderUnavailable,
    default_krx_base_date,
    fetch_krx_instruments,
    is_krx_open_api_ready,
)
from quantmate_api.models import BacktestRun, DailyPrice, DataImportJob, Instrument, Market, UserStrategy
from quantmate_api.strategy_engine import build_strategy_candidates


class AppMode(StrEnum):
    RESEARCH = "research"
    LIVE_READONLY = "live-readonly"
    LIVE_TRADING = "live-trading"


class HealthResponse(BaseModel):
    status: str
    app: str
    mode: AppMode
    live_trading_enabled: bool


class Strategy(BaseModel):
    code: str
    name: str
    source_type: str = "system"
    category: str
    style: str
    holding_period: str
    summary: str
    rebalance_rule: str
    data_requirements: list[str]
    universe_filter: list[str]
    signal_rules: list[str]
    ranking_rules: list[str]
    risk_controls: list[str]
    risk_notes: list[str]
    backtest_assumptions: list[str]
    references: list[str]
    default_enabled: bool = True


class Recommendation(BaseModel):
    symbol: str
    name: str
    market: str
    strategy_code: str
    score: int = Field(ge=0, le=100)
    signal: str
    rationale: list[str]
    risk_flags: list[str]


class StrategyCandidate(BaseModel):
    symbol: str
    name: str
    exchange: str
    sector: str
    industry: str
    market_cap: float
    price: int
    change_pct: float
    per: float
    pbr: float
    roe: float
    revenue_growth: float
    foreign_net_buy_5d: int
    institution_net_buy_5d: int
    supply_score: int
    short_sale_ratio: float
    momentum: int
    strategy_score: int = Field(ge=0, le=100)
    rationale: list[str]
    risk_flags: list[str]


class StrategyCandidateResponse(BaseModel):
    strategy_code: str
    strategy_name: str
    source: str
    candidates: list[StrategyCandidate]


class UserStrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    formula: str = Field(min_length=1, max_length=5000)
    result_count: int = Field(ge=0)


class UserStrategyResponse(BaseModel):
    id: int
    code: str
    name: str
    summary: str
    formula: str
    result_count: int
    created_at: datetime


class BacktestMetric(BaseModel):
    label: str
    value: str
    tone: str


class EquityPoint(BaseModel):
    day: str
    value: float


class BacktestPreview(BaseModel):
    strategy_code: str
    period: str
    assumptions: list[str]
    metrics: list[BacktestMetric]
    equity_curve: list[EquityPoint]


class BacktestRunRequest(BaseModel):
    strategy_code: str
    start_year: int = Field(ge=1990, le=2100)
    end_year: int = Field(ge=1990, le=2100)
    initial_amount: int = Field(gt=0)


class BacktestPerformanceMetric(BaseModel):
    metric: str
    value: str


class BacktestAnnualReturn(BaseModel):
    year: str
    portfolio_return: float
    yield_pct: float
    balance: int
    income: int


class BacktestEquityPoint(BaseModel):
    label: str
    portfolio: int


class BacktestRebalanceRow(BaseModel):
    date: str
    holdings: str
    entries: str
    exits: str
    turnover: str


class BacktestRunResponse(BaseModel):
    run_id: int | None = None
    strategy_code: str
    strategy_name: str
    source: str
    period: str
    initial_amount: int
    final_amount: int
    run_at: str
    notice: str
    metrics: list[BacktestPerformanceMetric]
    annual_returns: list[BacktestAnnualReturn]
    equity_curve: list[BacktestEquityPoint]
    rebalance_history: list[BacktestRebalanceRow]


class BacktestRunSummary(BaseModel):
    id: int
    strategy_code: str
    strategy_name: str
    period: str
    source: str
    initial_amount: int
    final_amount: int
    created_at: datetime


class DashboardResponse(BaseModel):
    as_of: date
    modes: list[dict[str, str | bool]]
    strategies: list[Strategy]
    recommendations: list[Recommendation]
    backtest: BacktestPreview


class DataStatusResponse(BaseModel):
    connected: bool
    provider_status: list[dict[str, str | bool]]
    table_counts: dict[str, int]
    message: str


class KrxInstrumentPreview(BaseModel):
    symbol: str
    name: str
    exchange: str
    asset_type: str


class KrxInstrumentPreviewResponse(BaseModel):
    provider: str
    market: str
    base_date: str
    count: int
    instruments: list[KrxInstrumentPreview]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _allowed_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOWED_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://127.0.0.1:5173", "http://localhost:5173"]


app = FastAPI(
    title="QuantMate API",
    version="0.1.0",
    description="Local API for Korean equity screening, backtesting, and future KIS broker integration.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


STRATEGIES = [
    Strategy(
        code="relative-momentum-swing",
        name="상대 모멘텀 스윙",
        category="모멘텀",
        style="1주~3개월 스윙",
        holding_period="1주~3개월",
        summary="최근 강한 종목 중 시장 대비 수익률과 유동성이 함께 확인되는 후보를 찾습니다.",
        rebalance_rule="주 1회 또는 월 1회 점검, 상위 후보 10~20개 교체",
        data_requirements=["일봉 OHLCV", "수정주가", "거래대금", "시장 대비 수익률"],
        universe_filter=["KOSPI/KOSDAQ 보통주", "거래정지/관리종목 제외", "거래대금 하위 종목 제외"],
        signal_rules=[
            "최근 3~12개월 수익률 상위",
            "최근 1개월 급등 과열 종목은 감점",
            "20일/60일 이동평균 위",
            "거래대금이 일정 수준 이상",
        ],
        ranking_rules=["상대수익률", "거래대금 증가", "추세 유지 점수", "과열 감점"],
        risk_controls=["급등 직후 추격 매수 감점", "시장 급락 구간 방어 규칙 필요", "거래량 급감 시 제외"],
        risk_notes=["횡보장과 급락장에서 성과가 나빠질 수 있음", "급등 직후 추격 매수 위험"],
        backtest_assumptions=["월 1회 리밸런싱", "상위 10개 동일 비중", "일봉 종가 기준 체결"],
        references=[
            "Jegadeesh & Titman (1993) 모멘텀 연구: https://www.jstor.org/stable/2328882",
            "Moskowitz, Ooi & Pedersen (2012) Time Series Momentum: https://ideas.repec.org/a/eee/jfinec/v104y2012i2p228-250.html",
        ],
    ),
    Strategy(
        code="value-quality-factor",
        name="가치/퀄리티 팩터",
        category="가치/퀄리티",
        style="수개월~1년 이상",
        holding_period="수개월~1년 이상",
        summary="싼 가격 지표와 나쁘지 않은 재무 품질을 함께 만족하는 중장기 후보를 찾습니다.",
        rebalance_rule="분기 또는 반기 점검, 재무 데이터 갱신 시 교체",
        data_requirements=["PER/PBR", "ROE", "부채비율", "영업이익률", "영업현금흐름"],
        universe_filter=["재무 데이터 결측 종목 제외", "적자 지속 종목 감점", "유동성 부족 종목 제외"],
        signal_rules=[
            "낮은 PER/PBR 또는 높은 이익수익률",
            "ROE와 영업현금흐름 양호",
            "부채비율 과도 종목 제외",
            "Piotroski F-Score식 재무 개선 신호 반영",
        ],
        ranking_rules=["밸류에이션 매력", "수익성", "재무 안정성", "재무 개선 점수"],
        risk_controls=["가치 함정 가능성 점검", "실적 악화 종목 제외", "재무 데이터 업데이트 지연 표시"],
        risk_notes=["가치 함정 가능성", "재무 데이터 업데이트 지연"],
        backtest_assumptions=["분기 리밸런싱", "상위 20개 동일 비중", "재무 발표 지연 반영"],
        references=[
            "Fama & French (2015) 5-factor model: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2287202",
            "Piotroski (2000) F-Score: https://www.jstor.org/stable/2672906",
        ],
    ),
    Strategy(
        code="growth-breakout-leader",
        name="성장 주도주 돌파형",
        category="성장/돌파",
        style="수주~수개월",
        holding_period="수주~수개월",
        summary="실적 성장과 가격 돌파가 동시에 나타나는 주도주 후보를 찾습니다.",
        rebalance_rule="주 1회 점검, 돌파 실패나 이동평균 이탈 시 제외",
        data_requirements=["일봉 OHLCV", "52주 신고가", "거래량", "매출/이익 성장률", "섹터 강도"],
        universe_filter=["거래대금 하위 종목 제외", "극단적 고평가 종목 감점", "적자 성장주 별도 표시"],
        signal_rules=[
            "매출 또는 이익 성장률 양호",
            "52주 신고가 근접 또는 박스권 상단 돌파",
            "돌파일 거래량 증가",
            "시장/섹터 상대강도 양호",
        ],
        ranking_rules=["성장률", "신고가 근접도", "돌파 거래량", "섹터 상대강도"],
        risk_controls=["고평가 성장주 급락 위험 표시", "돌파 실패 시 제외", "약세장 신호 품질 저하 반영"],
        risk_notes=["고평가 성장주 급락 위험", "약세장에서 신호 품질 저하"],
        backtest_assumptions=["주 1회 리밸런싱", "돌파 실패 시 다음 점검일 제외", "상위 10개 동일 비중"],
        references=[
            "George & Hwang (2004) 52-week high momentum: https://www.jstor.org/stable/3694815",
            "International 52-week high momentum evidence: https://ideas.repec.org/a/eee/jimfin/v30y2011i1p180-204.html",
        ],
    ),
    Strategy(
        code="trend-breakout",
        name="추세 돌파형",
        category="추세/돌파",
        style="단기~중기 트레이딩",
        holding_period="며칠~수개월",
        summary="20일 또는 55일 고가 돌파처럼 명확한 가격 채널 돌파가 나오는 종목을 찾습니다.",
        rebalance_rule="신호 발생 시 진입 후보 등록, 반대 신호나 손절 기준 도달 시 제외",
        data_requirements=["일봉 고가/저가/종가", "ATR", "거래대금", "이동평균"],
        universe_filter=["거래대금 부족 종목 제외", "변동성 과도 종목 감점", "갭 급등 종목 별도 표시"],
        signal_rules=[
            "20일 또는 55일 고가 돌파",
            "거래대금 증가",
            "ATR 기준 변동성 과도 종목 감점",
            "추세 이탈 또는 ATR 기반 손절 규칙 포함",
        ],
        ranking_rules=["돌파 강도", "거래대금 증가율", "ATR 대비 손익비", "추세 지속 점수"],
        risk_controls=["박스권 속임수 돌파 감점", "손절/청산 규칙 필수", "급등 갭 발생 시 진입 보류"],
        risk_notes=["박스권 장세에서 속임수 돌파가 많음", "손절/청산 규칙이 반드시 필요"],
        backtest_assumptions=["종가 돌파 기준 진입", "다음 거래일 시가 체결 가정", "ATR 기반 청산 비교"],
        references=[
            "Donchian channel breakout overview: https://www.investopedia.com/ask/answers/121714/how-are-donchian-channels-used-when-building-trading-strategies.asp",
            "Time-series momentum evidence: https://ideas.repec.org/a/eee/jfinec/v104y2012i2p228-250.html",
        ],
    ),
    Strategy(
        code="supply-demand-accumulation",
        name="수급 누적형",
        category="수급",
        style="며칠~수주 스윙",
        holding_period="며칠~수주",
        summary="외국인/기관 매수세가 누적되며 가격 추세가 개선되는 종목을 찾습니다.",
        rebalance_rule="주 1회 점검, 수급 반전 또는 가격 추세 훼손 시 제외",
        data_requirements=["투자자별 순매수", "일봉 OHLCV", "거래대금", "이동평균"],
        universe_filter=["수급 데이터 결측 종목 제외", "거래대금 부족 종목 제외", "단기 뉴스 급등 종목 감점"],
        signal_rules=[
            "외국인 또는 기관 5~20일 순매수 누적",
            "거래대금 증가",
            "가격이 이동평균을 회복하거나 유지",
            "단기 급등 과열 종목 감점",
        ],
        ranking_rules=["외국인 순매수", "기관 순매수", "거래대금 증가", "가격 추세 회복"],
        risk_controls=["수급 데이터 지연 표시", "뉴스성 단기 수급 감점", "매수세 반전 시 제외"],
        risk_notes=["수급 데이터 지연과 정정 가능성", "뉴스성 단기 수급은 쉽게 반전될 수 있음"],
        backtest_assumptions=["주 1회 리밸런싱", "상위 10개 후보 관찰", "수급 데이터 제공 지연 반영"],
        references=[
            "Korea investor flow data will be mapped from KRX/KIS once connected",
            "Momentum evidence used as price-trend confirmation: https://www.jstor.org/stable/2328882",
        ],
    ),
    Strategy(
        code="low-volatility-defensive",
        name="저변동성/방어형",
        category="방어형",
        style="중기~장기",
        holding_period="수개월~1년 이상",
        summary="변동성이 낮고 재무 안정성이 있는 종목을 찾아 공격형 전략의 보완 축으로 사용합니다.",
        rebalance_rule="월 1회 점검, 변동성 급등이나 재무 훼손 시 제외",
        data_requirements=["일봉 수익률 변동성", "MDD", "ROE", "부채비율", "거래대금"],
        universe_filter=["거래대금 부족 종목 제외", "재무 안정성 낮은 종목 제외", "저변동성 과열 종목 감점"],
        signal_rules=[
            "최근 6~12개월 변동성 낮음",
            "MDD 낮음",
            "재무 안정성 양호",
            "거래대금 부족 종목 제외",
        ],
        ranking_rules=["낮은 변동성", "낮은 MDD", "ROE 안정성", "밸류에이션 과열 감점"],
        risk_controls=["강한 상승장 소외 가능성 표시", "저변동성 과열 구간 감점", "유동성 부족 종목 제외"],
        risk_notes=["강한 상승장에서는 공격형 전략보다 뒤처질 수 있음", "저변동성이 비싸진 구간 주의"],
        backtest_assumptions=["월 1회 리밸런싱", "상위 20개 동일 비중", "변동성 급등 종목 제외"],
        references=[
            "Baker, Bradley & Wurgler (2011) Low-volatility anomaly: https://www.hbs.edu/faculty/Pages/item.aspx?num=39353",
            "Low-volatility anomaly paper: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1585031",
        ],
    ),
]

RECOMMENDATIONS = [
    Recommendation(
        symbol="005930",
        name="삼성전자",
        market="KOSPI",
        strategy_code="relative-momentum-swing",
        score=82,
        signal="관심",
        rationale=["시장 대표주로 유동성 우수", "단기 이동평균 회복", "거래대금 상위권"],
        risk_flags=["대형주는 급등 폭이 제한될 수 있음", "반도체 업황 뉴스 민감"],
    ),
    Recommendation(
        symbol="000660",
        name="SK하이닉스",
        market="KOSPI",
        strategy_code="growth-breakout-leader",
        score=78,
        signal="관찰",
        rationale=["섹터 모멘텀 양호", "실적 성장 기대 반영", "거래대금 상위권"],
        risk_flags=["반도체 업황 뉴스 민감"],
    ),
    Recommendation(
        symbol="012450",
        name="한화에어로스페이스",
        market="KOSPI",
        strategy_code="supply-demand-accumulation",
        score=76,
        signal="관심",
        rationale=["기관/외국인 동반 순매수 가정", "거래대금 증가", "가격 추세 양호"],
        risk_flags=["테마성 뉴스에 따른 변동성 확대 가능"],
    ),
    Recommendation(
        symbol="105560",
        name="KB금융",
        market="KOSPI",
        strategy_code="value-quality-factor",
        score=74,
        signal="관찰",
        rationale=["낮은 PBR", "ROE 안정성", "배당/자본정책 기대"],
        risk_flags=["금리와 경기 민감"],
    ),
]

BACKTEST = BacktestPreview(
    strategy_code="relative-momentum-swing",
    period="2023-01-02 ~ 2025-12-30 샘플",
    assumptions=[
        "선택 전략의 리밸런싱 규칙 사용",
        "왕복 거래 비용과 슬리피지는 백테스트 엔진 연결 후 전략 파라미터로 분리",
        "후보 종목은 전략 점수 상위 종목 기준",
        "현재 결과는 화면 검증용 샘플",
    ],
    metrics=[
        BacktestMetric(label="CAGR", value="18.4%", tone="positive"),
        BacktestMetric(label="MDD", value="-12.7%", tone="caution"),
        BacktestMetric(label="승률", value="57.8%", tone="neutral"),
        BacktestMetric(label="회전율", value="월 1.8회", tone="neutral"),
    ],
    equity_curve=[
        EquityPoint(day="2023-Q1", value=100.0),
        EquityPoint(day="2023-Q2", value=108.4),
        EquityPoint(day="2023-Q3", value=103.8),
        EquityPoint(day="2023-Q4", value=117.6),
        EquityPoint(day="2024-Q1", value=121.1),
        EquityPoint(day="2024-Q2", value=135.9),
        EquityPoint(day="2024-Q3", value=130.2),
        EquityPoint(day="2024-Q4", value=146.5),
        EquityPoint(day="2025-Q1", value=151.8),
        EquityPoint(day="2025-Q2", value=162.4),
        EquityPoint(day="2025-Q3", value=157.7),
        EquityPoint(day="2025-Q4", value=174.2),
    ],
)


def _find_system_strategy(strategy_code: str) -> Strategy | None:
    return next((item for item in STRATEGIES if item.code == strategy_code), None)


def _user_strategy_response(strategy: UserStrategy) -> UserStrategyResponse:
    return UserStrategyResponse(
        id=strategy.id,
        code=strategy.code,
        name=strategy.name,
        summary=strategy.summary,
        formula=strategy.formula,
        result_count=strategy.result_count,
        created_at=strategy.created_at,
    )


def _normalize_user_strategy_create(request: UserStrategyCreate) -> UserStrategyCreate:
    name = request.name.strip()
    summary = request.summary.strip()
    formula = request.formula.strip()

    if not name:
        raise HTTPException(status_code=422, detail="전략명을 입력하세요.")
    if not summary:
        raise HTTPException(status_code=422, detail="전략 소개를 입력하세요.")
    if not formula:
        raise HTTPException(status_code=422, detail="전략 조건식이 비어 있습니다.")

    return UserStrategyCreate(
        name=name,
        summary=summary,
        formula=formula,
        result_count=request.result_count,
    )


def _load_active_user_strategy(strategy_code: str) -> UserStrategy | None:
    try:
        with SessionLocal() as session:
            return session.scalar(
                select(UserStrategy).where(
                    UserStrategy.code == strategy_code,
                    UserStrategy.is_active.is_(True),
                )
            )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"사용자 전략 DB 연결 확인 필요: {exc.__class__.__name__}",
        ) from exc


def _save_backtest_run(
    *,
    result: dict[str, object],
    request: BacktestRunRequest,
) -> int | None:
    first_year = min(request.start_year, request.end_year)
    last_year = max(request.start_year, request.end_year)

    try:
        with SessionLocal() as session:
            run = BacktestRun(
                strategy_code=str(result["strategy_code"]),
                strategy_name=str(result["strategy_name"]),
                source=str(result["source"]),
                start_year=first_year,
                end_year=last_year,
                initial_amount=int(result["initial_amount"]),
                final_amount=int(result["final_amount"]),
                result_json=json.dumps(result, ensure_ascii=False),
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run.id
    except SQLAlchemyError:
        return None


def _backtest_summary(run: BacktestRun) -> BacktestRunSummary:
    return BacktestRunSummary(
        id=run.id,
        strategy_code=run.strategy_code,
        strategy_name=run.strategy_name,
        period=f"{run.start_year} ~ {run.end_year}",
        source=run.source,
        initial_amount=run.initial_amount,
        final_amount=run.final_amount,
        created_at=run.created_at,
    )


@app.get("/api/health")
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app="QuantMate API",
        mode=AppMode.RESEARCH,
        live_trading_enabled=_env_bool("LIVE_TRADING_ENABLED"),
    )


@app.get("/api/strategies")
async def list_strategies() -> list[Strategy]:
    return STRATEGIES


@app.get("/api/strategies/{strategy_code}/candidates")
async def strategy_candidates(strategy_code: str) -> StrategyCandidateResponse:
    strategy = _find_system_strategy(strategy_code)
    strategy_name = strategy.name if strategy else ""
    source = "sample-engine"

    if strategy is None and strategy_code.startswith("user-"):
        user_strategy = _load_active_user_strategy(strategy_code)
        if user_strategy is not None:
            strategy_name = user_strategy.name
            source = "sample-engine:user-strategy"

    if strategy is None and not strategy_name:
        raise HTTPException(status_code=404, detail="전략을 찾지 못했습니다.")

    return StrategyCandidateResponse(
        strategy_code=strategy_code,
        strategy_name=strategy_name,
        source=source,
        candidates=[
            StrategyCandidate(**candidate)
            for candidate in build_strategy_candidates(strategy_code=strategy_code)
        ],
    )


@app.get("/api/user-strategies")
async def list_user_strategies() -> list[UserStrategyResponse]:
    try:
        with SessionLocal() as session:
            rows = session.scalars(
                select(UserStrategy)
                .where(UserStrategy.is_active.is_(True))
                .order_by(UserStrategy.created_at.desc(), UserStrategy.id.desc())
            ).all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"사용자 전략 DB 연결 확인 필요: {exc.__class__.__name__}",
        ) from exc

    return [_user_strategy_response(row) for row in rows]


@app.post("/api/user-strategies", status_code=201)
async def create_user_strategy(request: UserStrategyCreate) -> UserStrategyResponse:
    normalized = _normalize_user_strategy_create(request)

    try:
        with SessionLocal() as session:
            strategy = UserStrategy(
                code=f"user-{uuid4().hex[:12]}",
                name=normalized.name,
                summary=normalized.summary,
                formula=normalized.formula,
                result_count=normalized.result_count,
            )
            session.add(strategy)
            session.commit()
            session.refresh(strategy)
            return _user_strategy_response(strategy)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"사용자 전략 DB 저장 실패: {exc.__class__.__name__}",
        ) from exc


@app.delete("/api/user-strategies/{strategy_code}")
async def delete_user_strategy(strategy_code: str) -> dict[str, bool]:
    try:
        with SessionLocal() as session:
            strategy = session.scalar(
                select(UserStrategy).where(
                    UserStrategy.code == strategy_code,
                    UserStrategy.is_active.is_(True),
                )
            )
            if strategy is None:
                raise HTTPException(status_code=404, detail="사용자 전략을 찾지 못했습니다.")

            strategy.is_active = False
            session.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"사용자 전략 DB 삭제 실패: {exc.__class__.__name__}",
        ) from exc

    return {"deleted": True}


@app.get("/api/recommendations")
async def list_recommendations() -> list[Recommendation]:
    return RECOMMENDATIONS


@app.get("/api/backtests/preview")
async def backtest_preview() -> BacktestPreview:
    return BACKTEST


@app.post("/api/backtests/run")
async def run_backtest(request: BacktestRunRequest) -> BacktestRunResponse:
    strategy = _find_system_strategy(request.strategy_code)
    strategy_name = strategy.name if strategy else ""

    if strategy is None and request.strategy_code.startswith("user-"):
        user_strategy = _load_active_user_strategy(request.strategy_code)
        strategy_name = user_strategy.name if user_strategy else ""

    if not strategy_name:
        raise HTTPException(status_code=404, detail="전략을 찾지 못했습니다.")

    result = build_sample_backtest(
        strategy_code=request.strategy_code,
        strategy_name=strategy_name,
        start_year=request.start_year,
        end_year=request.end_year,
        initial_amount=request.initial_amount,
    )
    result["run_id"] = _save_backtest_run(result=result, request=request)

    return BacktestRunResponse(**result)


@app.get("/api/backtests/runs")
async def list_backtest_runs(limit: int = 10) -> list[BacktestRunSummary]:
    safe_limit = max(1, min(limit, 50))

    try:
        with SessionLocal() as session:
            runs = session.scalars(
                select(BacktestRun)
                .order_by(BacktestRun.created_at.desc(), BacktestRun.id.desc())
                .limit(safe_limit)
            ).all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"백테스트 결과 DB 조회 실패: {exc.__class__.__name__}",
        ) from exc

    return [_backtest_summary(run) for run in runs]


@app.get("/api/dashboard")
async def dashboard() -> DashboardResponse:
    return DashboardResponse(
        as_of=date.today(),
        modes=[
            {"code": AppMode.RESEARCH.value, "label": "리서치", "enabled": True},
            {"code": AppMode.LIVE_READONLY.value, "label": "실계좌 읽기", "enabled": False},
            {"code": AppMode.LIVE_TRADING.value, "label": "실거래", "enabled": _env_bool("LIVE_TRADING_ENABLED")},
        ],
        strategies=STRATEGIES,
        recommendations=RECOMMENDATIONS,
        backtest=BACKTEST,
    )


@app.get("/api/data/status")
async def data_status() -> DataStatusResponse:
    krx_ready = is_krx_open_api_ready()
    provider_status = [
        {"name": "KIS Open API", "scope": "현재가/실시간/계좌", "status": "권한 필요", "ready": False},
        {"name": "FinanceDataReader", "scope": "종목 목록/일봉", "status": "후보", "ready": True},
        {
            "name": "KRX Open API",
            "scope": "공식 인증키 기반 종목/OHLCV",
            "status": "인증키 설정됨" if krx_ready else "API 인증키 필요",
            "ready": krx_ready,
        },
        {"name": "OpenDART", "scope": "재무제표/공시", "status": "API 키 필요", "ready": False},
    ]

    try:
        with SessionLocal() as session:
            table_counts = {
                "markets": session.scalar(select(func.count()).select_from(Market)) or 0,
                "instruments": session.scalar(select(func.count()).select_from(Instrument)) or 0,
                "daily_prices": session.scalar(select(func.count()).select_from(DailyPrice)) or 0,
                "data_import_jobs": session.scalar(select(func.count()).select_from(DataImportJob)) or 0,
                "user_strategies": session.scalar(select(func.count()).select_from(UserStrategy)) or 0,
                "backtest_runs": session.scalar(select(func.count()).select_from(BacktestRun)) or 0,
            }
    except SQLAlchemyError as exc:
        return DataStatusResponse(
            connected=False,
            provider_status=provider_status,
            table_counts={},
            message=f"DB 연결 확인 필요: {exc.__class__.__name__}",
        )

    return DataStatusResponse(
        connected=True,
        provider_status=provider_status,
        table_counts=table_counts,
        message="로컬 MySQL 연결 정상",
    )


@app.get("/api/data/krx/instruments")
async def krx_instruments(
    market: str = "KOSPI",
    limit: int = 50,
    base_date: str | None = None,
) -> KrxInstrumentPreviewResponse:
    effective_base_date = base_date or default_krx_base_date()

    try:
        instruments = fetch_krx_instruments(
            market=market,
            limit=limit,
            base_date=effective_base_date,
        )
    except MarketDataProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KrxInstrumentPreviewResponse(
        provider="KRX Open API",
        market=market.strip().upper(),
        base_date=effective_base_date,
        count=len(instruments),
        instruments=[KrxInstrumentPreview(**item) for item in instruments],
    )
