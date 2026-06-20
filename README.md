# QuantMate

QuantMate는 주식 종목 선정, 전략 연구, 백테스트, 선택형 모의 투자를 위한 로컬 우선 웹 애플리케이션입니다.

첫 대상 시장은 한국 주식입니다. 나중에 미국 주식까지 확장할 수 있게 구조는 열어두되, 초기 구현은 한국 주식 데이터, 알고리즘 기반 종목 선정, 안전한 증권사 연동에 집중합니다.

## 현재 상태

현재 저장소는 초기 앱 골격, 로컬 MySQL 스키마, 데모 데이터 상태 화면까지 구현한 단계입니다.

먼저 볼 문서:

- [프로젝트 개요](docs/00-project-brief.md)
- [초기 결정 사항](docs/01-initial-decisions.md)
- [작업 목록](docs/02-todo.md)
- [남은 질문](docs/03-open-questions.md)
- [작업 규칙](docs/04-working-rules.md)
- [참고 자료](docs/05-references.md)
- [로컬 설정](docs/06-local-setup.md)
- [스킬 운영 계획](docs/07-skills.md)

에이전트 작업 지침은 [AGENTS.md](AGENTS.md)를 기준으로 합니다.

## 로컬 실행

백엔드:

```bash
make install-backend
make backend-dev
```

프론트엔드:

```bash
make install-frontend
make frontend-dev
```

기본 주소:

- API: http://127.0.0.1:8000
- Web: http://127.0.0.1:5173

MySQL 마이그레이션:

```bash
make db-up
make db-migrate
make db-seed
```

## 안전 기준

이 프로젝트는 투자 연구와 자동화를 위한 소프트웨어입니다. 투자 조언이 아닙니다.

실거래 기능은 아래 항목이 구현되고 검토되기 전까지 비활성화 상태를 유지합니다.

- 모의 투자 모드
- 주문 금액 제한
- 일별 손실 및 주문 횟수 제한
- 긴급 중지 기능
- 모든 신호와 주문의 감사 로그
- 실거래 활성화 전 사용자 명시 확인
