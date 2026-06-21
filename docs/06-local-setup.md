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

한국투자증권 KIS Open API는 `.env`에만 아래 값을 입력한다. 기본은 앱이 `APP_KEY`와 `APP_SECRET`으로 접근토큰을 자동 발급하고 `.run/kis_token_cache.json`에 로컬 캐시한다. 개발 중 서버를 자주 재시작해도 캐시가 남아 있으면 같은 토큰을 재사용한다. KIS의 1분당 토큰 발급 제한에 걸릴 때만 `KIS_ACCESS_TOKEN`에 직접 발급받은 토큰을 임시로 넣는다.

```env
KIS_APP_KEY=발급받은_APP_KEY
KIS_APP_SECRET=발급받은_APP_SECRET
KIS_ACCESS_TOKEN=
KIS_ACCOUNT_NO=계좌번호_앞_8자리
KIS_ACCOUNT_PRODUCT_CODE=계좌번호_뒤_2자리
KIS_IS_PAPER=true
KIS_BASE_URL=https://openapivts.koreainvestment.com:29443
KIS_WS_URL=ws://ops.koreainvestment.com:31000
PAPER_TRADING_ENABLED=false
```

`PAPER_TRADING_ENABLED=false`는 모의투자 주문 제출 잠금이다. 계좌 상태와 잔고 조회는 이 값과 무관하게 읽기 전용으로 동작한다. 모의주문 제출은 이 값을 `true`로 바꾸고, 요청 본문에 `confirm_submit=true`를 넣은 경우에만 동작한다.

실전투자는 값을 교체하되 `LIVE_TRADING_ENABLED=false`를 유지하고, 실전 주문은 별도 안전장치 검토 전까지 사용하지 않는다.

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
curl "http://127.0.0.1:8000/api/data/kis/investor-trade-daily?symbol=005930&limit=20"
curl "http://127.0.0.1:8000/api/data/kis/daily-short-sale?symbol=005930&limit=20"
curl "http://127.0.0.1:8000/api/data/kis/daily-credit-balance?symbol=005930&limit=20"
curl "http://127.0.0.1:8000/api/data/kis/financial-ratios?symbol=005930&period_type=annual&limit=4"
curl "http://127.0.0.1:8000/api/data/kis/daily-prices?symbol=005930"
curl http://127.0.0.1:8000/api/broker/kis/account/status
curl http://127.0.0.1:8000/api/broker/kis/balance
curl "http://127.0.0.1:8000/api/broker/kis/buyable-cash?symbol=005930&order_type=market"
```

모의주문 제출 API는 `/api/broker/kis/paper/orders`다. 기본은 차단 상태이며, 주문 전후 감사 로그가 DB의 `broker_audit_logs`에 저장된다. 실제 주문 테스트는 주문 시점에 별도 확인 후 진행한다.

전략 후보와 백테스트 화면은 사용자가 별도 적재 버튼을 누르지 않아도 DB 일봉을 우선 사용한다. 데이터가 부족하면 서버가 KIS 시가총액 랭킹과 저장된 일봉 종목을 후보 시드로 삼아 KIS 일봉을 먼저 자동 수집하고, KIS 커버리지가 부족한 종목은 Yahoo/yfinance 일봉으로 보완해 `daily_prices`에 저장한 뒤 계산한다. 전략 후보 조회 시에는 KIS 재무비율을 `fundamental_ratios`에 저장해 ROE, 성장률, 부채비율을 보강하고, KIS 투자자별 매매동향을 `supply_flow_dailies`에 저장해 외국인/기관/연기금 수급 필드를 보강하며, 공매도/신용잔고 일별 지표를 `risk_indicator_dailies`에 저장해 리스크 필드를 보강한다. 공급원 우선순위는 종목별로 `KRX Open API -> KIS Open API -> Yahoo Finance`이며, KRX 승인 전에는 KIS와 Yahoo를 혼합해 사용한다.

전략 후보 API가 실제 일봉을 사용하면 응답의 `source`가 `daily-price-candidates:KIS Open API + Yahoo Finance`처럼 표시된다. KIS 현재가 스냅샷으로 PER/PBR/시가총액/회전율을 보강한 경우 `+ KIS 현재가`, 재무비율을 보강한 경우 `+ KIS 재무`가 함께 표시된다. 백테스트 결과도 `daily-price-backtest:<공급원>` 형식의 `source`를 저장한다.

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
