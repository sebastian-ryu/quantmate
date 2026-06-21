---
name: quantmate-strategy-backtest
description: QuantMate에서 전략 카탈로그, 전략 후보 선정, 검색기 조건식, 사용자 등록 전략, 백테스트 실행/저장/재조회, 비교군 차트, 성과지표를 구현하거나 수정할 때 사용한다. strategy_engine.py, backtest_engine.py, 전략/백테스트 Svelte 화면, 검색기 조건 매핑 작업이 트리거다.
---

# QuantMate 전략/백테스트

## 핵심 계약

- 전략은 검색, 백테스트, 주문 제안이 공유하는 하나의 계약이어야 한다.
- 시스템 전략과 사용자 등록 전략을 구분해서 표시한다.
- 검색기에서 저장한 조건식은 전략 후보와 백테스트에서 같은 방식으로 해석한다.
- 백테스트는 고정 종목 포트폴리오가 아니라 조건에 따른 동적 후보 선정과 리밸런싱을 전제로 한다.
- 사용자에게 보이는 날짜와 금액은 한국시간, 원화 기준으로 표현한다.

## 주요 파일

- 전략 후보: `backend/src/quantmate_api/strategy_engine.py`
- 백테스트 엔진: `backend/src/quantmate_api/backtest_engine.py`
- API 계약: `backend/src/quantmate_api/main.py`
- 프론트 API 타입: `frontend/src/lib/api.ts`
- 검색기 화면: `frontend/src/routes/screener/+page.svelte`
- 전략 화면: `frontend/src/routes/strategy/+page.svelte`
- 백테스트 화면: `frontend/src/routes/strategies/+page.svelte`
- 조건 맵 문서: `docs/09-screener-condition-map.md`

## 변경 순서

1. 전략 데이터 계약과 조건식 필드명을 먼저 정한다.
2. 백엔드 엔진과 API 응답을 수정한다.
3. 프론트 타입과 화면을 같은 계약에 맞춘다.
4. 조건식, 후보 선정, 백테스트 저장/재조회 테스트를 추가한다.
5. `docs/02-todo.md`, `docs/08-strategy-catalog.md`, `docs/09-screener-condition-map.md`를 갱신한다.

## 검증

- `python3 -m pytest backend/tests`
- `python3 -m ruff check backend/src backend/tests`
- `npm --prefix frontend run check`
- 차트나 레이아웃 변경은 브라우저에서 전략/백테스트/검색기 화면을 확인한다.
