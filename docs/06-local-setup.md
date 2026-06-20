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

백엔드 설치에는 KRX Open API 호출에 필요한 HTTP 클라이언트가 포함된다.

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
