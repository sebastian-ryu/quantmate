# 로컬 설정

## Docker

이 프로젝트는 로컬 MySQL 실행에 Docker Compose를 사용한다.

Docker 확인:

```bash
docker --version
docker compose version
```

Docker가 설치되어 있지 않다면 Mac용 Docker Desktop을 설치한다.

https://docs.docker.com/desktop/setup/install/mac-install/

설치 후 Docker Desktop을 한 번 실행하고, 실행 완료 상태가 될 때까지 기다린다.

## 환경 파일

로컬 환경 파일을 만든다.

```bash
cp .env.example .env
```

그다음 `.env`를 열어 실제 사용 전에 로컬 비밀번호를 바꾼다.

`.env`는 커밋하지 않는다.

앱 기준 시간대는 `APP_TIMEZONE=Asia/Seoul`로 둔다. 사용자 입력, 화면 표시, DB 저장, 거래일 표현은 한국시간 기준이다.

## MySQL

MySQL 시작:

```bash
docker compose up -d mysql
```

상태 확인:

```bash
docker compose ps
docker compose logs -f mysql
```

컨테이너 안의 MySQL CLI로 접속:

```bash
docker compose exec mysql mysql -uquantmate -p quantmate
```

MySQL 중지:

```bash
docker compose down
```

로컬 MySQL 데이터 볼륨 삭제:

```bash
docker compose down -v
```

`down -v`는 로컬 DB 데이터를 의도적으로 지울 때만 사용한다.

MySQL 컨테이너는 `TZ=Asia/Seoul`과 `--default-time-zone=+09:00`으로 실행한다. 로컬에서 별도 MySQL을 직접 사용할 경우에도 세션/서버 시간대를 한국시간으로 맞춘다.

마이그레이션 적용:

```bash
make db-migrate
```

초기 개발용 데모 종목 입력:

```bash
make db-seed
```

## 백엔드

의존성 설치:

```bash
make install-backend
```

백엔드 설치에는 KRX Open API 호출에 필요한 HTTP 클라이언트와 Yahoo 임시 일봉 수집용 `yfinance`가 포함된다.

한국투자증권 KIS Open API는 `.env`에만 아래 값을 입력한다. 기본은 앱이 `APP_KEY`와 `APP_SECRET`으로 접근토큰을 자동 발급하고 `.run/kis_token_cache.json`에 로컬 캐시한다. 개발 중 서버를 자주 재시작해도 캐시가 남아 있으면 같은 토큰을 재사용한다. KIS의 1분당 토큰 발급 제한에 걸릴 때만 `KIS_ACCESS_TOKEN`에 직접 발급받은 토큰을 임시로 넣는다. WebSocket 접속키도 서버가 `/oauth2/Approval`로 자동 발급해 `.run/kis_ws_approval_cache.json`에 저장한다. `KIS_WS_APPROVAL_KEY`는 자동 발급이 어려운 상황에서만 임시로 사용한다.

```env
KIS_APP_KEY=발급받은_APP_KEY
KIS_APP_SECRET=발급받은_APP_SECRET
KIS_ACCESS_TOKEN=
KIS_ACCOUNT_NO=계좌번호_앞_8자리
KIS_ACCOUNT_PRODUCT_CODE=계좌번호_뒤_2자리
KIS_IS_PAPER=true
KIS_BASE_URL=https://openapivts.koreainvestment.com:29443
KIS_WS_URL=ws://ops.koreainvestment.com:31000
KIS_WS_APPROVAL_KEY=
KIS_WS_APPROVAL_CACHE_PATH=
KIS_REALTIME_MAX_SYMBOLS=20
PAPER_TRADING_ENABLED=false
LIVE_TRADING_ENABLED=false
EMERGENCY_STOP_ENABLED=false
MANUAL_ORDER_CONFIRMATION_REQUIRED=true
DAILY_LOSS_STOP_ENABLED=false
MAX_ORDER_AMOUNT_KRW=5000000
MAX_DAILY_ORDER_COUNT=10
MAX_DAILY_LOSS_KRW=50000
```

`PAPER_TRADING_ENABLED=false`는 모의투자 주문 제출 잠금이다. 계좌 상태와 잔고 조회는 이 값과 무관하게 읽기 전용으로 동작한다. 모의주문 제출은 이 값을 `true`로 바꾸고, 요청 본문에 `confirm_submit=true`를 넣은 경우에만 동작한다.
주문 제출 전 서버는 `MAX_ORDER_AMOUNT_KRW`, `MAX_DAILY_ORDER_COUNT`, `EMERGENCY_STOP_ENABLED`, `MANUAL_ORDER_CONFIRMATION_REQUIRED`를 검사한다. 기본 1회 주문 한도는 `5,000,000원`이며, 시장가 주문은 KIS 현재가로 예상 주문금액을 계산한다. `DAILY_LOSS_STOP_ENABLED=true`면 주문 제출 직전에 KIS 잔고를 조회해 전일 대비 자산 감소액이 `MAX_DAILY_LOSS_KRW` 이상인지 확인한다.

실전투자는 값을 교체하되 `LIVE_TRADING_ENABLED=false`를 유지하고, 실전 주문은 별도 안전장치 검토 전까지 사용하지 않는다.

시장 데이터 호출은 기본적으로 429/5xx 응답과 일시 네트워크 오류에 짧게 재시도한다. 필요하면 `.env`에서 아래 값을 조정한다.

데이터 공급원은 백엔드 provider registry에서 역할별로 관리한다. 현재 일봉 우선순위는 `KRX Open API -> KIS Open API -> Yahoo Finance`이며, KRX 일봉은 인증 승인 후 구현할 수 있도록 어댑터 자리만 열어두었다.
OpenDART 공시/재무제표 연동을 준비할 경우 `.env`에 아래 값을 입력한다. 서버는 고유번호 ZIP을 받아 `.run/opendart_corp_codes.json`에 캐시하고, 단일회사 전체 재무제표 조회 API로 종목별 재무제표 행과 매출/이익/마진/부채비율/ROE/ROA 요약 지표를 확인할 수 있다.

```env
OPEN_DART_API_KEY=발급받은_OPEN_DART_API_KEY
OPEN_DART_BASE_URL=https://opendart.fss.or.kr/api
OPEN_DART_CORP_CODE_CACHE_PATH=
OPENDART_REQUEST_MIN_INTERVAL_SECONDS=0.2
```

확인용 API:

```bash
curl http://127.0.0.1:8000/api/data/opendart/corp-codes/status
curl -X POST "http://127.0.0.1:8000/api/data/opendart/corp-codes/cache?force_refresh=true"
curl "http://127.0.0.1:8000/api/data/opendart/financial-statements?symbol=005930&business_year=2025&report_code=11011&fs_div=CFS"
```

미국 시장 확장을 위한 NYSE/Nasdaq 정규 휴장일 캘린더도 제공한다. 현재는 정규 휴장일 계산만 포함하고 조기폐장은 별도 확장 대상으로 둔다.

```bash
curl "http://127.0.0.1:8000/api/data/market-calendar?market=NASDAQ&start=2026-06-18&end=2026-06-22"
```

```env
MARKET_DATA_RETRY_COUNT=2
MARKET_DATA_RETRY_BACKOFF_SECONDS=0.6
KIS_REQUEST_MIN_INTERVAL_SECONDS=0.08
YAHOO_REQUEST_MIN_INTERVAL_SECONDS=0.2
KRX_REQUEST_MIN_INTERVAL_SECONDS=0.2
```

```env
# KIS_IS_PAPER=false
# KIS_BASE_URL=https://openapi.koreainvestment.com:9443
# KIS_WS_URL=ws://ops.koreainvestment.com:21000
```

현재 구현된 KIS 읽기 전용 확인용 API:

```bash
curl http://127.0.0.1:8000/api/data/kis/token/status
curl "http://127.0.0.1:8000/api/data/kis/current-price?symbol=005930"
curl "http://127.0.0.1:8000/api/data/kis/market-cap-ranking?market=KOSPI&limit=10"
curl -X POST http://127.0.0.1:8000/api/data/kis/instruments/import \
  -H "Content-Type: application/json" \
  -d '{"market":"ALL","limit":100}'
curl "http://127.0.0.1:8000/api/data/kis/investor-trade-daily?symbol=005930&limit=20"
curl "http://127.0.0.1:8000/api/data/kis/daily-short-sale?symbol=005930&limit=20"
curl "http://127.0.0.1:8000/api/data/kis/daily-credit-balance?symbol=005930&limit=20"
curl "http://127.0.0.1:8000/api/data/kis/financial-ratios?symbol=005930&period_type=annual&limit=4"
curl "http://127.0.0.1:8000/api/data/kis/daily-prices?symbol=005930"
curl http://127.0.0.1:8000/api/data/kis/websocket/approval/status
curl -X POST http://127.0.0.1:8000/api/data/kis/websocket/approval-key \
  -H "Content-Type: application/json" \
  -d '{"force_refresh":false}'
curl http://127.0.0.1:8000/api/data/kis/realtime/quotes/status
curl -X POST http://127.0.0.1:8000/api/data/kis/realtime/quotes/subscribe \
  -H "Content-Type: application/json" \
  -d '{"symbols":["005930","000660"]}'
curl http://127.0.0.1:8000/api/data/kis/realtime/quotes/latest
curl -X POST http://127.0.0.1:8000/api/data/kis/realtime/quotes/stop
curl http://127.0.0.1:8000/api/broker/kis/account/status
curl http://127.0.0.1:8000/api/broker/kis/safety-status
curl http://127.0.0.1:8000/api/broker/kis/balance
curl "http://127.0.0.1:8000/api/broker/kis/buyable-cash?symbol=005930&order_type=market"
curl http://127.0.0.1:8000/api/broker/kis/orders
```

모의주문 제출 API는 `/api/broker/kis/paper/orders`다. 기본은 차단 상태이며, 주문 전후 감사 로그가 DB의 `broker_audit_logs`에 저장된다. 최근 주문체결 내역은 `/api/broker/kis/orders`로 읽기 전용 조회한다. 실제 주문 테스트는 주문 시점에 별도 확인 후 진행한다.

전략 후보와 백테스트 화면은 사용자가 별도 적재 버튼을 누르지 않아도 DB 일봉을 우선 사용한다. 데이터가 부족하면 서버가 KIS 시가총액 랭킹과 저장된 일봉 종목을 후보 시드로 삼아 KIS 일봉을 먼저 자동 수집하고, KIS 커버리지가 부족한 종목과 기간은 Yahoo/yfinance 일봉으로 보완해 `daily_prices`에 저장한 뒤 계산한다. `/api/data/kis/instruments/import`는 KIS 시가총액 랭킹으로 확인한 종목 코드와 종목명을 `instruments`에 저장한다. 현재는 KIS가 제공하는 랭킹 기반 universe 저장이며, 완전한 전체 종목 마스터는 KRX 종목기본정보 승인 후 보완한다. 전략 후보 조회 시에는 KIS 재무비율을 `fundamental_ratios`에 저장해 ROE, 성장률, 부채비율을 보강하고, KIS 투자자별 매매동향이 있으면 외국인/기관/연기금 수급 필드를 보강하며, 공매도/신용잔고 일별 지표를 `risk_indicator_dailies`에 저장해 리스크 필드를 보강한다. 공급원 우선순위는 종목별로 `KRX Open API -> KIS Open API -> Yahoo Finance`이지만, 백테스트는 요청한 시작연도와 종료연도를 더 길게 커버하는 공급원을 먼저 선택한다. 따라서 KIS 데이터가 짧고 Yahoo 데이터가 더 길면 백테스트는 Yahoo를 사용하고, KRX 승인 후 충분한 KRX 일봉이 저장되면 KRX를 우선 사용한다.

전략 후보 API가 실제 일봉을 사용하면 응답의 `source`가 `daily-price-candidates:KIS Open API + Yahoo Finance`처럼 표시된다. KIS 현재가 스냅샷으로 PER/PBR/시가총액/회전율을 보강한 경우 `+ KIS 현재가`, 재무비율을 보강한 경우 `+ KIS 재무`가 함께 표시된다. 백테스트 결과도 `daily-price-backtest:<공급원>` 형식의 `source`를 저장한다.

백테스트 자산 곡선과 비교군 곡선의 첫 월은 사용자가 입력한 초기투자금으로 표시한다. 비교군은 선택 기간의 첫 거래일 종가를 기준가로 삼고, 이후 각 월말 종가를 `초기투자금 * 월말종가 / 첫 거래일 종가`로 환산한다.

검색기에서 저장한 사용자 전략은 백엔드가 저장된 조건식을 1차 해석해 후보에 적용한다. 현재 해석 가능한 조건은 키워드, 거래소, 섹터, 산업, 가격, 모멘텀, 등락률, PER/PBR/ROE, 거래량 배율, 이동평균 위치 등이다. 아직 공급원 필드가 부족한 세부 조건은 후보에서 제외하지 않고 위험 표시로 남긴다.

검색기 화면의 결과 목록은 `/api/screener/search`를 사용한다. 서버가 검색식 조건을 해석한 뒤 실제 일봉 기반 가격/모멘텀/등락 데이터와 KIS 현재가/재무/수급/공매도/신용잔고 보조 필드를 함께 반환한다. 검색기는 전략 화면보다 넓은 후보 풀을 요청하므로, 이미 DB에 저장된 실제 일봉 종목까지 포함해 결과를 확장한다. 재무 세부 조건 중 아직 공급원 필드가 부족한 항목은 보조값 또는 0으로 표시되며, KIS/KRX/OpenDART 매핑 후 교체한다.

KRX 데이터는 ID/PW가 아니라 KRX Open API 인증키를 사용한다. 인증키는 `.env`의 `KRX_OPEN_API_AUTH_KEY`에만 입력하고 커밋하지 않는다.

KRX Open API는 인증키 발급과 서비스별 이용신청이 별도다. 종목 목록과 일봉 데이터를 쓰려면 최소 아래 서비스를 신청한다.

- 유가증권 종목기본정보
- 코스닥 종목기본정보
- 유가증권 일별매매정보
- 코스닥 일별매매정보

승인 전에는 인증키가 있어도 API 호출이 401로 실패할 수 있다.

개발 서버 실행:

```bash
make backend-dev
```

백엔드는 기본적으로 http://127.0.0.1:8000 에서 실행된다.

상태 확인:

```bash
curl http://127.0.0.1:8000/api/health
```

## 프론트엔드

의존성 설치:

```bash
make install-frontend
```

개발 서버 실행:

```bash
make frontend-dev
```

웹 UI는 기본적으로 http://127.0.0.1:5173 에서 실행된다.
