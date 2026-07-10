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

## 백업

최소 백업 대상은 아래 세 가지다.

- MySQL 데이터 폴더 또는 DB dump
- `.env`
- backend runtime 폴더

`.env`에는 API 키와 계좌 정보가 있으므로 별도 암호화 저장소에 보관한다.
