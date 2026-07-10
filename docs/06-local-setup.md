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
PUBLIC_SHOW_PAPER_TRADING_UI=true
PAPER_TRADING_ENABLED=false
LIVE_TRADING_ENABLED=false
EMERGENCY_STOP_ENABLED=false
MANUAL_ORDER_CONFIRMATION_REQUIRED=true
DAILY_LOSS_STOP_ENABLED=false
MAX_ORDER_AMOUNT_KRW=5000000
MAX_DAILY_ORDER_COUNT=10
MAX_DAILY_LOSS_KRW=50000
```

`PUBLIC_SHOW_PAPER_TRADING_UI=false`는 전략 화면에서 KIS 모의투자 계좌, 주문 제안, 모의 일괄 주문 영역을 아예 숨긴다. `PAPER_TRADING_ENABLED=false`는 화면 표시 여부와 별개인 서버 주문 제출 잠금이다. 계좌 상태와 잔고 조회는 이 값과 무관하게 읽기 전용으로 동작한다. 모의주문 제출은 이 값을 `true`로 바꾸고, 요청 본문에 `confirm_submit=true`를 넣은 경우에만 동작한다.
주문 제출 전 서버는 `MAX_ORDER_AMOUNT_KRW`, `MAX_DAILY_ORDER_COUNT`, `EMERGENCY_STOP_ENABLED`, `MANUAL_ORDER_CONFIRMATION_REQUIRED`를 검사한다. 기본 1회 주문 한도는 `5,000,000원`이며, 시장가 주문은 KIS 현재가로 예상 주문금액을 계산한다. `DAILY_LOSS_STOP_ENABLED=true`면 주문 제출 직전에 KIS 잔고를 조회해 전일 대비 자산 감소액이 `MAX_DAILY_LOSS_KRW` 이상인지 확인한다.

실전투자는 값을 교체하되 `LIVE_TRADING_ENABLED=false`를 유지하고, 실전 주문은 별도 안전장치 검토 전까지 사용하지 않는다.

시장 데이터 호출은 기본적으로 429/5xx 응답과 일시 네트워크 오류에 짧게 재시도한다. 필요하면 `.env`에서 아래 값을 조정한다.

데이터 공급원은 백엔드 provider registry에서 역할별로 관리한다. 현재 일봉 우선순위는 `KRX Open API -> KIS Open API -> Yahoo Finance`이며, KRX 일봉 미리보기/DB 적재 API는 구현되어 있다. KRX는 인증키 발급과 서비스별 승인 상태가 모두 충족되어야 실제 호출이 성공한다. 승인 완료 후에는 KRX 종목기본정보와 일별매매정보를 공식 한국 주식 마스터/장기 일봉 공급원으로 사용한다.
OpenDART 공시/재무제표 연동을 준비할 경우 `.env`에 아래 값을 입력한다. 서버는 고유번호 ZIP을 받아 `.run/opendart_corp_codes.json`에 캐시하고, 단일회사 전체 재무제표 조회 API로 종목별 재무제표 행과 매출/이익/마진/부채비율/ROE/ROA 요약 지표를 확인할 수 있다. 저장 API를 호출하거나 전략 후보를 열면 OpenDART 요약이 `fundamental_ratios`에 저장되어 검색기/전략 후보 재무 필드 보강에 사용된다.

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
curl -X POST "http://127.0.0.1:8000/api/data/opendart/financial-statements/import?symbol=005930&business_year=2025&report_code=11011&fs_div=CFS"
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
KRX_DAILY_PRICE_MAX_DAYS=370
KIS_CURRENT_QUOTE_MAX_AGE_MINUTES=10
KIS_CURRENT_QUOTE_REFRESH_MAX_SYMBOLS=30
STRATEGY_DAILY_PRICE_MAX_STALENESS_DAYS=1
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

전략 후보와 백테스트 화면은 사용자가 별도 적재 버튼을 누르지 않아도 DB 일봉을 우선 사용한다. 전략 후보 API는 기본적으로 `refresh=true`로 동작해 조회 시 KIS 일봉, 현재가, 재무, 수급, 리스크 보조 데이터를 가능한 범위에서 먼저 갱신한다. 전략 후보 계산용 일봉이 기대 거래일보다 `STRATEGY_DAILY_PRICE_MAX_STALENESS_DAYS` 이상 지연되어 있으면 KIS 일봉 갱신을 먼저 시도하고, 응답의 `data_freshness.daily_price_status`와 `warnings`에 지연 여부를 남긴다. 검색기 API도 화면에 표시되는 개별 종목 가격/등락/거래대금이 과거 일봉에 머물지 않도록 현재가 스냅샷을 갱신한다. KIS 현재가 스냅샷이 있으면 가격, 당일 등락률, 거래대금, 거래량, 시가총액, PER, PBR은 현재가 스냅샷을 우선 표시하고, 갱신 후 전략 점수와 선정 사유를 다시 계산한다. `KIS_CURRENT_QUOTE_MAX_AGE_MINUTES`가 지난 스냅샷은 다시 조회하며, 한 번에 자동 갱신할 후보 수는 `KIS_CURRENT_QUOTE_REFRESH_MAX_SYMBOLS`로 제한한다. 데이터가 부족하면 서버가 KIS 시가총액 랭킹과 저장된 일봉 종목을 후보 시드로 삼아 KIS 일봉을 먼저 자동 수집하고, KIS 커버리지가 부족한 종목과 기간은 Yahoo/yfinance 일봉으로 보완해 `daily_prices`에 저장한 뒤 계산한다. `/api/data/kis/instruments/import`는 KIS 시가총액 랭킹으로 확인한 종목 코드와 종목명을 `instruments`에 저장한다. `/api/data/krx/instruments/import`는 KRX 종목기본정보로 KRX 종목 마스터를 `instruments`에 저장한다. `/api/data/krx/daily-prices/import`는 단일 종목 KRX 원천 일봉을 `daily_prices`에 저장하고, `/api/data/krx/daily-prices/import/market`은 KOSPI/KOSDAQ/KONEX 또는 ALL 시장의 일자별 전체 일봉을 한 번에 저장한다. 전략 후보 조회 시에는 KIS 재무비율을 `fundamental_ratios`에 저장해 ROE, 성장률, 부채비율을 보강하고, KIS 투자자별 매매동향이 있으면 외국인/기관/연기금 수급 필드를 보강하며, 공매도/신용잔고 일별 지표를 `risk_indicator_dailies`에 저장해 리스크 필드를 보강한다. 공급원 우선순위는 종목별로 `KRX Open API -> KIS Open API -> Yahoo Finance`이지만, 백테스트는 요청한 시작연도와 종료연도를 더 길게 커버하는 공급원을 먼저 선택한다. 따라서 KIS 데이터가 짧고 Yahoo 데이터가 더 길면 백테스트는 Yahoo를 사용하고, KRX 승인 후 충분한 KRX 일봉이 저장되면 KRX를 우선 사용한다.

DB를 가능한 최신으로 유지하는 운영 전략은 세 단계다. 장 시작 전에는 종목 마스터와 전일 일봉을 갱신하고, 장중에는 전략/검색기 조회 시 화면 후보의 KIS 현재가 스냅샷을 짧은 TTL로 갱신하며, 장 종료 후에는 KIS 또는 KRX 일봉을 다시 적재해 다음 백테스트와 전략 계산의 기준 DB를 최신화한다. Synology Docker 배포 후에는 Container Manager 예약 작업이나 NAS 스케줄러에서 이 적재 API를 호출하는 방식으로 자동화한다.

자동 예약 전에는 전략/검색기 화면 상단의 `최신 데이터 갱신` 버튼으로 KRX 종목 마스터와 KOSPI/KOSDAQ 최근 일봉을 수동 갱신한다. 버튼을 누르면 `/api/data/manual-refresh`가 백그라운드 Job을 만들고, 화면은 `/api/data/manual-refresh/{job_id}`를 주기적으로 조회해 현재 단계, 진행률, 저장 건수, 경과 시간, 예상 남은 시간을 표시한다. 완료 후에는 현재 화면의 전략 후보 또는 검색기 결과를 다시 조회해 데이터 기준일과 공급원 표시를 갱신한다. 현재 1차 구현은 KRX 종목 마스터와 KRX 최근 일봉 갱신이 대상이며, KIS 현재가/재무/수급/리스크와 배당 데이터 범위 선택은 후속 작업이다.

초기 장기 일봉 적재는 `최신 데이터 갱신` 버튼이 아니라 `scripts/krx-backfill-daily-prices.sh`를 사용한다. 기본값은 `2010년~현재`, `KOSPI KOSDAQ`이며, KRX 시장 일봉 API를 연도별로 나누어 호출한다.

전략 후보 API가 실제 일봉을 사용하면 응답의 `source`가 `daily-price-candidates:KIS Open API + Yahoo Finance`처럼 표시된다. KIS 현재가 스냅샷으로 PER/PBR/시가총액/회전율을 보강한 경우 `+ KIS 현재가`, 재무비율을 보강한 경우 `+ KIS 재무`가 함께 표시된다. 백테스트 결과도 `daily-price-backtest:<공급원>` 형식의 `source`를 저장한다.

전략 설명 카드의 최근 1년/3년/5년/10년 성과는 `/api/strategies/performance`에서 별도 계산한다. 이 값은 기대수익률 예측이 아니라 저장된 DB 일봉 기준 백테스트 CAGR, 총수익률, MDD이며, 한국시간 날짜, 최신 일봉 거래일, `daily_prices` 저장 건수가 바뀌면 캐시를 무효화한다. 강제 재계산이 필요하면 `/api/strategies/performance?refresh=true`를 호출한다.

백테스트 자산 곡선과 비교군 곡선의 첫 월은 사용자가 입력한 초기투자금으로 표시한다. 비교군은 선택 기간의 첫 거래일 종가를 기준가로 삼고, 이후 각 월말 종가를 `초기투자금 * 월말종가 / 첫 거래일 종가`로 환산한다.

검색기에서 저장한 사용자 전략은 백엔드가 저장된 조건식을 1차 해석해 후보에 적용한다. 현재 해석 가능한 조건은 키워드, 거래소, 섹터, 산업, 가격, 모멘텀, 등락률, PER/PBR/ROE, 거래량 배율, 이동평균 위치 등이다. 아직 공급원 필드가 부족한 세부 조건은 후보에서 제외하지 않고 위험 표시로 남긴다.

검색기 화면의 결과 목록은 `/api/screener/search`를 사용한다. 서버가 검색식 조건을 해석한 뒤 실제 일봉 기반 가격/모멘텀/등락 데이터와 KIS 현재가/재무/수급/공매도/신용잔고 보조 필드를 함께 반환한다. 검색기는 전략 화면보다 넓은 후보 풀을 요청하므로, 이미 DB에 저장된 실제 일봉 종목까지 포함해 결과를 확장한다. 재무 세부 조건 중 아직 공급원 필드가 부족한 항목은 보조값 또는 0으로 표시되며, KIS/KRX/OpenDART 매핑 후 교체한다.

KRX 데이터는 ID/PW가 아니라 KRX Open API 인증키를 사용한다. 인증키는 `.env`의 `KRX_OPEN_API_AUTH_KEY`에만 입력하고 커밋하지 않는다.

KRX Open API는 인증키 발급과 서비스별 이용신청이 별도다. 종목 목록과 일봉 데이터를 쓰려면 최소 아래 서비스를 신청한다.

- 유가증권 종목기본정보
- 코스닥 종목기본정보
- 유가증권 일별매매정보
- 코스닥 일별매매정보
- 코넥스 종목기본정보와 코넥스 일별매매정보는 코넥스까지 포함할 때 신청

승인 전에는 인증키가 있어도 API 호출이 401로 실패할 수 있다.

KRX 종목기본정보 저장 확인:

```bash
curl "http://127.0.0.1:8000/api/data/krx/instruments?market=KOSPI&limit=5"
curl "http://127.0.0.1:8000/api/data/krx/daily-prices?symbol=005930&exchange=KOSPI&start=2026-06-01&end=2026-06-30"
curl -X POST http://127.0.0.1:8000/api/data/krx/instruments/import \
  -H "Content-Type: application/json" \
  -d '{"market":"ALL","limit":3000}'
curl -X POST http://127.0.0.1:8000/api/data/krx/daily-prices/import \
  -H "Content-Type: application/json" \
  -d '{"symbol":"005930","name":"삼성전자","exchange":"KOSPI","start":"2026-06-01","end":"2026-06-30"}'
curl -X POST http://127.0.0.1:8000/api/data/krx/daily-prices/import/market \
  -H "Content-Type: application/json" \
  -d '{"market":"KOSPI","start":"2026-06-01","end":"2026-06-30"}'
```

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
