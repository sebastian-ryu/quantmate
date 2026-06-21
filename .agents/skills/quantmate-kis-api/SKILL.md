---
name: quantmate-kis-api
description: QuantMate에서 한국투자증권 KIS Open API 인증, 접근토큰, WebSocket 접속키, 실시간 시세, 계좌 조회, 모의주문, 주문 안전장치를 구현하거나 수정할 때 사용한다. KIS_APP_KEY, KIS_APP_SECRET, KIS_IS_PAPER, PAPER_TRADING_ENABLED, LIVE_TRADING_ENABLED, 주문 한도, 감사 로그, KIS REST/WebSocket 연동 파일을 다루는 작업이 트리거다.
---

# QuantMate KIS API

## 절차

1. 먼저 `AGENTS.md`, `docs/04-working-rules.md`, `docs/06-local-setup.md`, `docs/adr/0005-extended-market-data-policy.md`를 확인한다.
2. 비밀 정보는 `.env`에만 둔다. `.env.example`에는 이름, 기본값, 주석만 추가한다.
3. 실거래 주문은 `LIVE_TRADING_ENABLED=false`를 기본으로 유지한다. 실거래 주문 API는 사용자 검토 전 구현하지 않는다.
4. 모의주문도 `PAPER_TRADING_ENABLED`, `EMERGENCY_STOP_ENABLED`, `MANUAL_ORDER_CONFIRMATION_REQUIRED`, `MAX_ORDER_AMOUNT_KRW`, `MAX_DAILY_ORDER_COUNT`를 통과해야 한다.
5. KIS 호출 코드는 `backend/src/quantmate_api/market_data.py`에 두고, API 라우트는 `backend/src/quantmate_api/main.py`에 둔다.
6. WebSocket 실시간 시세는 읽기 전용으로 시작하고, 체결통보/주문 상태 동기화는 정책과 테스트를 먼저 둔다.
7. 새 KIS 응답은 사용자에게 원문 토큰, 계좌번호, 승인키가 노출되지 않도록 마스킹하거나 저장하지 않는다.

## 검증

- 백엔드 변경 후 `python3 -m pytest backend/tests`를 실행한다.
- 정적 검사로 `python3 -m ruff check backend/src backend/tests`를 실행한다.
- 프론트 화면을 건드렸으면 `npm --prefix frontend run check`를 실행한다.
- 문서 영향이 있으면 `docs/02-todo.md`, `docs/06-local-setup.md`, 관련 ADR을 갱신한다.
