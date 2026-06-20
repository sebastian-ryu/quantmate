from __future__ import annotations

import os
from datetime import date
from enum import StrEnum

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from quantmate_api.db import SessionLocal
from quantmate_api.models import DailyPrice, DataImportJob, Instrument, Market


class AppMode(StrEnum):
    RESEARCH = "research"
    PAPER = "paper"
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
    style: str
    summary: str
    data_requirements: list[str]
    risk_notes: list[str]
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
    description="Local API for Korean equity screening, backtesting, and paper trading.",
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
        code="momentum-core",
        name="모멘텀 기본형",
        style="1-10일 스윙",
        summary="최근 상승 강도와 거래대금 증가를 함께 보는 기본 후보 선정 전략입니다.",
        data_requirements=["일봉 OHLCV", "거래대금", "이동평균"],
        risk_notes=["급등 직후 추격 매수 위험", "거래량이 급감하면 신호 신뢰도 하락"],
    ),
    Strategy(
        code="supply-demand-watch",
        name="수급 관심형",
        style="장중/스윙",
        summary="외국인/기관 순매수 흐름과 거래대금 변화를 함께 보는 전략입니다.",
        data_requirements=["투자자별 매매 동향", "일봉 OHLCV", "거래대금"],
        risk_notes=["수급 데이터 지연 가능성", "뉴스성 단기 수급 왜곡 가능성"],
    ),
    Strategy(
        code="quality-value",
        name="퀄리티 가치형",
        style="수주-수개월",
        summary="ROE, 부채비율, PBR 등 기본 지표로 안정적인 중기 후보를 찾습니다.",
        data_requirements=["재무제표", "PER/PBR", "ROE", "부채비율"],
        risk_notes=["재무 데이터 업데이트 지연", "가치 함정 가능성"],
    ),
]

RECOMMENDATIONS = [
    Recommendation(
        symbol="005930",
        name="삼성전자",
        market="KOSPI",
        strategy_code="momentum-core",
        score=82,
        signal="관심",
        rationale=["20일 거래대금 평균 상회", "단기 이동평균 회복", "시장 대표주로 유동성 우수"],
        risk_flags=["대형주는 급등 폭이 제한될 수 있음"],
    ),
    Recommendation(
        symbol="000660",
        name="SK하이닉스",
        market="KOSPI",
        strategy_code="momentum-core",
        score=78,
        signal="관찰",
        rationale=["섹터 모멘텀 양호", "최근 변동성 확대", "거래대금 상위권"],
        risk_flags=["반도체 업황 뉴스 민감"],
    ),
    Recommendation(
        symbol="035720",
        name="카카오",
        market="KOSPI",
        strategy_code="supply-demand-watch",
        score=71,
        signal="조건부 관심",
        rationale=["낙폭 이후 거래량 회복", "단기 추세 전환 후보", "수급 확인 필요"],
        risk_flags=["중장기 추세 확인 전"],
    ),
]

BACKTEST = BacktestPreview(
    strategy_code="momentum-core",
    period="2023-01-02 ~ 2025-12-30 샘플",
    assumptions=[
        "일봉 종가 기준 리밸런싱",
        "왕복 거래 비용 0.25% 가정",
        "슬리피지 0.10% 가정",
        "상위 10개 종목 동일 비중",
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


@app.get("/api/recommendations")
async def list_recommendations() -> list[Recommendation]:
    return RECOMMENDATIONS


@app.get("/api/backtests/preview")
async def backtest_preview() -> BacktestPreview:
    return BACKTEST


@app.get("/api/dashboard")
async def dashboard() -> DashboardResponse:
    return DashboardResponse(
        as_of=date.today(),
        modes=[
            {"code": AppMode.RESEARCH.value, "label": "리서치", "enabled": True},
            {"code": AppMode.PAPER.value, "label": "모의 투자", "enabled": _env_bool("PAPER_TRADING_ENABLED", True)},
            {"code": AppMode.LIVE_READONLY.value, "label": "실계좌 읽기", "enabled": False},
            {"code": AppMode.LIVE_TRADING.value, "label": "실거래", "enabled": _env_bool("LIVE_TRADING_ENABLED")},
        ],
        strategies=STRATEGIES,
        recommendations=RECOMMENDATIONS,
        backtest=BACKTEST,
    )


@app.get("/api/data/status")
async def data_status() -> DataStatusResponse:
    provider_status = [
        {"name": "KIS Open API", "scope": "현재가/실시간/계좌", "status": "권한 필요", "ready": False},
        {"name": "FinanceDataReader", "scope": "종목 목록/일봉", "status": "후보", "ready": True},
        {"name": "pykrx", "scope": "KRX 일봉/시장 데이터", "status": "후보", "ready": True},
        {"name": "OpenDART", "scope": "재무제표/공시", "status": "API 키 필요", "ready": False},
    ]

    try:
        with SessionLocal() as session:
            table_counts = {
                "markets": session.scalar(select(func.count()).select_from(Market)) or 0,
                "instruments": session.scalar(select(func.count()).select_from(Instrument)) or 0,
                "daily_prices": session.scalar(select(func.count()).select_from(DailyPrice)) or 0,
                "data_import_jobs": session.scalar(select(func.count()).select_from(DataImportJob)) or 0,
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
