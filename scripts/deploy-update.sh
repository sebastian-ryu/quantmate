#!/usr/bin/env sh
set -eu

SERVICE="${1:-all}"
COMPOSE_FILE="${DEPLOY_COMPOSE_FILE:-docker-compose.prod.yml}"
DOCKER_HOME="${DEPLOY_DOCKER_HOME:-/volume1/docker/quantmate/docker-home}"
USE_SUDO="${DEPLOY_USE_SUDO:-true}"
SKIP_GIT_PULL="${DEPLOY_SKIP_GIT_PULL:-false}"
API_HEALTH_URL="${DEPLOY_API_HEALTH_URL:-http://127.0.0.1:8000/api/health}"
FRONTEND_HEALTH_URL="${DEPLOY_FRONTEND_HEALTH_URL:-http://127.0.0.1:5173}"

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "오류: $COMPOSE_FILE 파일을 찾지 못했습니다. 프로젝트 루트에서 실행되는지 확인하세요." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "오류: git 명령을 찾지 못했습니다." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "오류: docker 명령을 찾지 못했습니다." >&2
  exit 1
fi

compose() {
  if [ "$USE_SUDO" = "true" ]; then
    sudo env HOME="$DOCKER_HOME" docker compose -f "$COMPOSE_FILE" "$@"
  else
    HOME="$DOCKER_HOME" docker compose -f "$COMPOSE_FILE" "$@"
  fi
}

health_check() {
  label="$1"
  url="$2"
  if command -v curl >/dev/null 2>&1; then
    if curl --max-time 10 -fsS "$url" >/dev/null; then
      echo "확인 완료: $label 응답 정상 ($url)"
    else
      echo "주의: $label 응답 확인 실패 ($url)" >&2
      return 1
    fi
  else
    echo "참고: curl이 없어 $label 헬스체크를 건너뜁니다."
  fi
}

echo "QuantMate 배포 업데이트 시작"
echo "- 대상 서비스: $SERVICE"
echo "- Compose 파일: $COMPOSE_FILE"

if [ "$SKIP_GIT_PULL" != "true" ]; then
  echo "Git 최신 코드 가져오는 중..."
  git pull --ff-only
else
  echo "Git pull 건너뜀: DEPLOY_SKIP_GIT_PULL=true"
fi

echo "이미지 빌드 및 컨테이너 재시작 중..."
case "$SERVICE" in
  all)
    compose up -d --build
    ;;
  backend|frontend|mysql)
    compose up -d --build "$SERVICE"
    ;;
  *)
    echo "오류: 지원하지 않는 서비스입니다: $SERVICE" >&2
    echo "사용법: sh scripts/deploy-update.sh [all|backend|frontend|mysql]" >&2
    exit 1
    ;;
esac

echo "컨테이너 상태:"
compose ps

if [ "$SERVICE" = "all" ] || [ "$SERVICE" = "backend" ]; then
  health_check "Backend API" "$API_HEALTH_URL" || true
fi

if [ "$SERVICE" = "all" ] || [ "$SERVICE" = "frontend" ]; then
  health_check "Frontend Web" "$FRONTEND_HEALTH_URL" || true
fi

echo "QuantMate 배포 업데이트 완료"
