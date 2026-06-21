---
name: quantmate-doc-sync
description: QuantMate에서 코드, 데이터 소스, 전략 계약, 화면 구조, 환경변수, 실행 방법, 매매 안전 정책이 바뀐 뒤 프로젝트 문서를 최신화할 때 사용한다. docs/02-todo.md, docs/06-local-setup.md, docs/09-screener-condition-map.md, ADR, .env.example, AGENTS.md를 점검하는 작업이 트리거다.
---

# QuantMate 문서 동기화

## 점검 순서

1. 변경된 파일을 `git status --short`와 `git diff --name-only`로 확인한다.
2. 기능 상태가 바뀌었으면 `docs/02-todo.md` 체크박스를 갱신한다.
3. 환경변수가 추가/변경되면 `.env.example`과 `docs/06-local-setup.md`에 설명을 추가한다.
4. 전략, 검색기 조건, 백테스트 계약이 바뀌면 `docs/08-strategy-catalog.md` 또는 `docs/09-screener-condition-map.md`를 갱신한다.
5. 데이터 공급원, 시간대, 매매 안전 정책이 바뀌면 `docs/adr/` 문서를 확인한다.
6. 사용자 의사결정이 필요한 항목은 완료 처리하지 말고 TODO 또는 open question으로 남긴다.

## 원칙

- 문서는 한국어로 작성한다.
- 구현되지 않은 기능을 완료로 표시하지 않는다.
- 비밀 정보, 실제 토큰, 계좌번호는 문서에 쓰지 않는다.
- 사용자에게 보이는 시간 기준은 한국시간으로 설명한다.

## 검증

- 문서만 수정해도 `git diff --check`를 실행한다.
- 코드와 함께 수정했다면 해당 코드 검증 명령을 함께 실행한다.
