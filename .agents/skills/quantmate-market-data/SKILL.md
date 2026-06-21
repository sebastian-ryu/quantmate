---
name: quantmate-market-data
description: QuantMate에서 KRX Open API, KIS Open API, Yahoo/yfinance, OpenDART, 시장/거래소/통화/시간대 메타데이터, 일봉 OHLCV, 재무/수급/리스크 데이터 적재와 provider priority를 구현하거나 수정할 때 사용한다. market_data.py, providers.py, daily_prices, instruments, data import API, 데이터 품질 검사 작업이 트리거다.
---

# QuantMate 데이터 수집

## 원칙

- 백테스트와 전략 엔진은 외부 API가 아니라 정규화된 DB 테이블을 읽게 유지한다.
- 데이터에는 제공처, 수집 이력, 수정주가 여부를 남긴다.
- KRX는 승인 후 공식 장기 일봉 공급원, KIS는 현재가/일봉/재무/수급/리스크/계좌, Yahoo는 임시 일봉 보완으로 사용한다.
- 사용자 화면, DB 저장 날짜, 거래일 표현은 한국시간 기준으로 설명한다.
- 미국 시장 확장은 종목코드, 통화, 시간대, 캘린더를 한국 시장과 분리해서 다룬다.

## 주요 파일

- 공급원 호출: `backend/src/quantmate_api/market_data.py`
- 공급원 registry: `backend/src/quantmate_api/providers.py`
- 저장 모델: `backend/src/quantmate_api/models.py`
- API 라우트와 저장 함수: `backend/src/quantmate_api/main.py`
- 로컬 설정: `.env.example`, `docs/06-local-setup.md`
- 공급원 정책: `docs/adr/0003-data-provider-priority.md`, `docs/adr/0005-extended-market-data-policy.md`

## 변경 순서

1. 어떤 데이터가 전략/백테스트/검색기에서 필요한지 먼저 확인한다.
2. 공급원별 권한, 호출 제한, 응답 필드, 결측 가능성을 확인한다.
3. `market_data.py`에 호출과 정규화를 추가하고 provider registry에 역할을 연결한다.
4. DB 저장이 필요하면 모델, 저장 함수, 테스트를 함께 추가한다.
5. 검색기/전략 후보에서 사용하는 필드명과 단위를 `docs/09-screener-condition-map.md`와 맞춘다.

## 검증

- API 호출은 네트워크 의존 테스트 대신 monkeypatch로 응답을 고정한다.
- `python3 -m pytest backend/tests`
- `python3 -m ruff check backend/src backend/tests`
- `git diff --check`
