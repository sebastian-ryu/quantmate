# QuantMate

QuantMate는 주식 종목 선정, 전략 연구, 백테스트를 위한 로컬 우선 웹 애플리케이션입니다.

첫 대상 시장은 한국 주식입니다. 나중에 미국 주식까지 확장할 수 있게 구조는 열어두되, 초기 구현은 한국 주식 데이터, 알고리즘 기반 종목 선정, 백테스트에 집중합니다. 데이터 수집과 향후 매매 연동은 한국투자증권 KIS Open API를 우선 사용하고, KRX Open API는 서비스별 승인 후 백테스트용 공식 장기 일봉 데이터 소스로 사용합니다.

## 현재 상태

현재 저장소는 검색기, 전략, 백테스트 중심의 로컬 웹 UI와 기본 전략 카탈로그, 전략 후보 실행 API, 검색기 전용 조회 API, 사용자 등록 전략 DB 저장, 백테스트 결과 저장/조회, 로컬 MySQL 스키마를 구현한 단계입니다. 전략 후보 산출과 검색기 결과는 DB 일봉을 우선 사용하고, KIS 시가총액 랭킹과 저장된 일봉 종목으로 후보 풀을 넓히며, KIS 현재가, 재무비율, 투자자별 매매동향, 공매도, 신용잔고가 있으면 PER/PBR/시총/회전율/재무/수급/리스크 필드를 보강합니다. 백테스트는 KRX 일봉이 있으면 KRX를 우선 사용하고, KRX가 없으면 KIS 일봉을 먼저 자동 갱신한 뒤 부족한 종목과 기간을 Yahoo/yfinance 일봉으로 보완해 계산합니다. 저장된 백테스트는 다시 불러와 차트를 볼 수 있고, KOSPI 200, KOSDAQ 대표지수, S&P 500, Nasdaq 100 비교군을 같은 초기투자금 기준으로 함께 표시할 수 있습니다. 모든 공급원이 실패할 때만 화면 검증용 샘플 결과로 대체합니다.

NAS 초기 배포 후 장기 백테스트용 KRX 일봉은 `scripts/krx-backfill-daily-prices.sh`로 적재합니다. 기본값은 2010년부터 현재까지 KOSPI/KOSDAQ 일봉이며, KRX API 제한을 피하기 위해 연도별로 나누어 저장합니다.

먼저 볼 문서:

- [프로젝트 개요](docs/00-project-brief.md)
- [초기 결정 사항](docs/01-initial-decisions.md)
- [작업 목록](docs/02-todo.md)
- [남은 질문](docs/03-open-questions.md)
- [작업 규칙](docs/04-working-rules.md)
- [참고 자료](docs/05-references.md)
- [로컬 설정](docs/06-local-setup.md)
- [스킬 운영 계획](docs/07-skills.md)
- [전략 카탈로그](docs/08-strategy-catalog.md)
- [Synology Docker 배포](docs/10-synology-deployment.md)

에이전트 작업 지침은 [AGENTS.md](AGENTS.md)를 기준으로 합니다.

## 로컬 실행

최초 1회 설치:

```bash
make install-backend
make install-frontend
```

전체 실행:

```bash
make dev
```

전체 종료:

```bash
make dev-stop
```

`make dev`는 MySQL, DB 마이그레이션, 백엔드 API, 프론트엔드 웹 서버를 함께 실행합니다. 실행 후 아래 주소를 사용합니다.

`make dev-stop`은 이 프로젝트의 기본 개발 포트인 8000, 5173 프로세스와 MySQL 컨테이너를 함께 종료합니다.

- Web: http://127.0.0.1:5173
- API: http://127.0.0.1:8000

로그 확인:

```bash
make dev-logs
```

서버를 따로 실행해야 할 때:

```bash
make backend-dev
make frontend-dev
```

MySQL 마이그레이션:

```bash
make db-up
make db-migrate
make db-seed
```

## Docker 배포

Synology DS224+ 같은 NAS에는 운영용 Compose 파일을 사용한다.

```bash
make prod-build
make prod-up
make prod-logs
make prod-down
```

자세한 절차와 NAS 경로 설정은 [Synology Docker 배포](docs/10-synology-deployment.md)를 본다.

## 안전 기준

이 프로젝트는 투자 연구와 자동화를 위한 소프트웨어입니다. 투자 조언이 아닙니다.

실거래 기능은 아래 항목이 구현되고 검토되기 전까지 비활성화 상태를 유지합니다.

- 한국투자증권 모의투자 또는 실거래 API 연동 계획
- 주문 금액 제한
- 일별 손실 및 주문 횟수 제한
- 긴급 중지 기능
- 모든 신호와 주문의 감사 로그
- 실거래 활성화 전 사용자 명시 확인

현재 KIS 모의투자 계좌는 읽기 전용 잔고 조회, 매수가능금액 조회, 최근 주문체결 조회까지 앱에 연결되어 있습니다. 모의주문 제출 API는 구현되어 있지만 `PAPER_TRADING_ENABLED=true`와 요청별 `confirm_submit=true`가 모두 있어야 동작하며, 1회 주문금액과 일일 주문 횟수 한도를 서버에서 검사합니다. 주문 전후 내용은 `broker_audit_logs`에 저장됩니다. 실전 주문은 계속 비활성화 상태로 둡니다.
