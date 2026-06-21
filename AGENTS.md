# QuantMate 에이전트 지침

이 파일은 이 저장소에서 작업하는 AI 에이전트가 우선 확인해야 하는 규칙 문서다.

## 기본 원칙

- 사용자에게 전달하는 답변은 간결하게 한다.
- 질문은 가능하면 한 번에 하나씩 한다.
- 작업 전 현재 문서와 작업 목록을 확인한다.
- 설계가 바뀌면 관련 문서를 함께 업데이트한다.
- 비밀 정보, API 키, 계좌 정보, 토큰은 절대 커밋하지 않는다.

## 우선 확인할 문서

- `docs/00-project-brief.md`: 프로젝트 목표와 범위
- `docs/01-initial-decisions.md`: 현재 기술 결정
- `docs/02-todo.md`: 단계별 작업 목록
- `docs/03-open-questions.md`: 남은 질문과 확정 답변
- `docs/04-working-rules.md`: 세부 작업 규칙
- `docs/07-skills.md`: 프로젝트 스킬 운영 계획

## 프로젝트 스킬

- `.agents/skills/quantmate-kis-api`: KIS 인증, 실시간 시세, 모의주문, 주문 안전장치 작업
- `.agents/skills/quantmate-market-data`: KRX/KIS/Yahoo/OpenDART 데이터 수집과 공급원 작업
- `.agents/skills/quantmate-strategy-backtest`: 전략 후보, 검색기 조건식, 백테스트 계약 작업
- `.agents/skills/quantmate-ui-qa`: 검색기, 전략, 백테스트 UI 구현과 브라우저 검증 작업
- `.agents/skills/quantmate-doc-sync`: 코드 변경 후 문서와 TODO 최신화 작업

## 현재 기본 방향

- 백엔드: Python + FastAPI
- 웹 클라이언트: SvelteKit + TypeScript
- 데이터베이스: Docker Compose 기반 MySQL 8.4 LTS
- 첫 시장: 한국 주식
- 첫 MVP: 종목 추천, 백테스트
- 실거래: 마지막 단계이며 기본 비활성화

## 증권 API 권한 처리

증권 관련 API에서 접근 권한, 계좌 신청, 토큰, 인증 정보가 필요하면 임의로 진행하지 않는다.

대신 사용자에게 필요한 작업을 한 번에 하나씩 질문하며 권한을 확보한 뒤 진행한다.

예:

- 한국투자증권 API 신청 여부 확인
- 한국투자증권 모의투자용 App Key/App Secret 발급 여부 확인
- KRX 승인 지연 시 Yahoo/yfinance를 임시 백테스트 데이터로 사용할지 확인
- 실계좌 접근 권한 필요 여부 확인
- `.env`에 넣어야 할 환경 변수 안내

## 문서 업데이트 규칙

다음 상황에서는 문서 업데이트를 먼저 검토한다.

- 기술 스택 변경
- 데이터 소스 변경
- 매매 안전 정책 변경
- 증권사 API 연동 방식 변경
- MVP 범위 변경
- 작업 순서 변경

## 안전 규칙

- 실거래 주문 기능은 데이터 수집, 종목 선정, 백테스트, 한국투자증권 모의투자 연동 계획이 검토되기 전에는 구현하지 않는다.
- 모든 주문 관련 기능은 서버 쪽 제한을 가져야 한다.
- 한국투자증권 모의투자와 실거래는 UI와 로그에서 명확히 구분해야 한다.
- 실거래 전에는 긴급 중지 기능과 주문 한도 설정이 필요하다.
- 초기 데이터 연동은 KIS를 우선하고, KRX는 승인 후 백테스트용 공식 장기 데이터 공급원으로 붙인다. KRX 승인 지연 시 Yahoo/yfinance는 임시 백테스트 데이터로만 사용한다.
- 사용자 입력, 화면 표시, DB 저장, 거래일 표현은 기본적으로 `Asia/Seoul` 한국시간을 사용한다. UTC는 외부 API 변환 등 내부적으로 불가피한 경우에만 쓰고 사용자에게 노출하지 않는다.
