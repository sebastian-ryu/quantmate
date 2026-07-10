# Synology Docker 배포

이 문서는 Synology DS224+의 Container Manager에서 QuantMate를 Docker Compose로 배포하기 위한 기준이다.

## 구성

운영 배포는 `docker-compose.prod.yml`을 사용한다.

- `mysql`: MySQL 8.4 데이터베이스
- `backend`: FastAPI API 서버, 시작 시 Alembic 마이그레이션 적용
- `frontend`: SvelteKit Node 서버

개발용 `docker-compose.yml`은 MySQL만 띄우는 용도이므로 NAS 배포에는 사용하지 않는다.

## 사전 준비

NAS에 아래 폴더를 만든다. 경로는 예시이며 `.env`에서 바꿀 수 있다.

```text
/volume1/docker/quantmate/mysql
/volume1/docker/quantmate/backend-runtime
/volume1/docker/quantmate/backend-logs
```

로컬 또는 NAS 배포 폴더에 `.env`를 만들고 최소 아래 값을 운영 환경에 맞게 설정한다.

```env
APP_ENV=prod
APP_TIMEZONE=Asia/Seoul
CORS_ALLOWED_ORIGINS=http://NAS_IP:5173
PUBLIC_API_BASE_URL=http://NAS_IP:8000
PUBLIC_SHOW_PAPER_TRADING_UI=false

MYSQL_DATABASE=quantmate
MYSQL_USER=quantmate
MYSQL_PASSWORD=운영_DB_비밀번호
MYSQL_ROOT_PASSWORD=운영_ROOT_비밀번호
MYSQL_PUBLIC_PORT=3306

QM_MYSQL_DATA_PATH=/volume1/docker/quantmate/mysql
QM_BACKEND_RUNTIME_PATH=/volume1/docker/quantmate/backend-runtime
QM_BACKEND_LOG_PATH=/volume1/docker/quantmate/backend-logs

KIS_APP_KEY=
KIS_APP_SECRET=
KIS_ACCOUNT_NO=
KIS_ACCOUNT_PRODUCT_CODE=
KIS_IS_PAPER=true
KIS_BASE_URL=https://openapivts.koreainvestment.com:29443
KIS_WS_URL=ws://ops.koreainvestment.com:31000

KRX_OPEN_API_AUTH_KEY=
OPEN_DART_API_KEY=
PAPER_TRADING_ENABLED=false
LIVE_TRADING_ENABLED=false
```

`NAS_IP`는 실제 NAS 접속 주소로 바꾼다. 브라우저가 직접 API를 호출하므로 `PUBLIC_API_BASE_URL`은 컨테이너 이름이 아니라 사용자의 브라우저에서 접근 가능한 주소여야 한다.

`MYSQL_PUBLIC_PORT`는 내부망 GUI DB 클라이언트 접속용이다. Synology 방화벽에서 Mac IP 또는 내부망 대역만 TCP 3306을 허용하고, 공유기 포트포워딩으로 3306을 외부에 열지 않는다.

## 실행

로컬에서 먼저 이미지 빌드가 되는지 확인한다.

```bash
make prod-build
```

NAS 또는 동일한 Compose 환경에서 실행한다.

```bash
make prod-up
```

로그 확인:

```bash
make prod-logs
```

중지:

```bash
make prod-down
```

## Container Manager에서 사용할 때

1. QuantMate 프로젝트 폴더를 NAS에 복사한다.
2. `.env`를 NAS 환경에 맞게 만든다.
3. Container Manager의 프로젝트 생성에서 `docker-compose.prod.yml`을 선택한다.
4. 최초 실행 후 `backend` 로그에서 마이그레이션 성공 여부를 확인한다.
5. 브라우저에서 `http://NAS_IP:5173`으로 접속한다.

## 데이터와 캐시

- MySQL 데이터는 `QM_MYSQL_DATA_PATH`에 저장한다.
- KIS 접근토큰, WebSocket 접속키, OpenDART 고유번호 캐시는 `QM_BACKEND_RUNTIME_PATH`에 저장한다.
- 백엔드 로그는 `QM_BACKEND_LOG_PATH`에 저장한다.

운영에서 `docker compose down -v`는 사용하지 않는다. MySQL 볼륨이 삭제될 수 있다.

## MySQL GUI 클라이언트 접속

운영 Compose는 MySQL을 `MYSQL_PUBLIC_PORT`로 NAS에 노출한다. 내부망에서 GUI 클라이언트로 접속할 때는 아래 값을 사용한다.

```text
Host: NAS_IP
Port: 3306
Database: quantmate
User: quantmate
Password: .env의 MYSQL_PASSWORD
```

보안 기준:

- Synology 방화벽에서 TCP 3306은 Mac IP 또는 신뢰하는 내부망 대역만 허용한다.
- 공유기에서 3306 포트포워딩을 설정하지 않는다.
- DB 클라이언트는 `root`가 아니라 `MYSQL_USER` 계정을 사용한다.
- `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`는 운영용 강한 비밀번호를 사용한다.

## 초기 KRX 장기 일봉 적재

NAS에 처음 배포한 뒤 장기 백테스트용 일봉을 채우려면 웹 버튼이 아니라 1회성 스크립트를 사용한다. 웹의 `최신 데이터 갱신` 버튼은 최근 데이터 유지용이며, 기본적으로 최근 10일만 갱신한다.

앱이 실행 중인지 먼저 확인한다.

```bash
cd /volume1/docker/quantmate/app
sudo env HOME=/volume1/docker/quantmate/docker-home docker compose -f docker-compose.prod.yml ps
```

기본 실행은 2010년부터 현재까지 KOSPI/KOSDAQ 일봉을 연도별로 나누어 적재한다.

```bash
cd /volume1/docker/quantmate/app
sh scripts/krx-backfill-daily-prices.sh
```

특정 기간만 다시 적재하려면 아래처럼 실행한다.

```bash
BACKFILL_START_YEAR=2020 \
BACKFILL_END_YEAR=2021 \
BACKFILL_MARKETS="KOSPI KOSDAQ" \
  sh scripts/krx-backfill-daily-prices.sh
```

주요 옵션:

- `BACKFILL_START_YEAR`: 시작 연도, 기본값 `2010`
- `BACKFILL_END_YEAR`: 종료 연도, 기본값 현재 연도
- `BACKFILL_MARKETS`: 적재 시장, 기본값 `KOSPI KOSDAQ`
- `BACKFILL_IMPORT_INSTRUMENTS`: 시작 전 KRX 종목 마스터 갱신 여부, 기본값 `true`
- `BACKFILL_CONTINUE_ON_ERROR`: 실패 구간이 있어도 다음 구간을 계속 진행할지 여부, 기본값 `false`
- `BACKFILL_DRY_RUN`: 실제 호출 없이 실행 계획만 출력, 기본값 `false`
- `BACKFILL_LOG_DIR`: 로그 저장 폴더, 기본값 `./runtime/logs/backfill`

스크립트는 KRX API의 1회 조회 제한을 피하기 위해 연도별로 API를 호출한다. 실패하면 로그의 마지막 `오류` 항목에 시장과 기간이 남으므로, 해당 기간만 다시 실행한다. 이 작업은 KRX 일별매매정보 서비스 권한과 `KRX_OPEN_API_AUTH_KEY`가 정상이어야 성공한다.

## 백업

최소 백업 대상은 아래 세 가지다.

- MySQL 데이터 폴더 또는 DB dump
- `.env`
- backend runtime 폴더

`.env`에는 API 키와 계좌 정보가 있으므로 별도 암호화 저장소에 보관한다.
