#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/logs"

mkdir -p "$RUN_DIR" "$LOG_DIR"

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

port_in_use() {
  local port="$1"
  command -v lsof >/dev/null 2>&1 && lsof -ti "tcp:$port" -sTCP:LISTEN >/dev/null 2>&1
}

wait_for_mysql() {
  local container_id
  container_id="$(docker compose -f "$ROOT_DIR/docker-compose.yml" ps -q mysql)"

  if [[ -z "$container_id" ]]; then
    echo "MySQL 컨테이너를 찾지 못했습니다."
    exit 1
  fi

  for _ in {1..40}; do
    local status
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
    if [[ "$status" == "healthy" || "$status" == "running" ]]; then
      return
    fi
    sleep 1
  done

  echo "MySQL 준비 시간이 초과되었습니다. 로그를 확인하세요: make db-logs"
  exit 1
}

start_managed_process() {
  local name="$1"
  local port="$2"
  local pid_file="$3"
  local log_file="$4"
  shift 4

  if is_running "$pid_file"; then
    echo "$name 이미 실행 중: PID $(cat "$pid_file")"
    return
  fi

  rm -f "$pid_file"

  if port_in_use "$port"; then
    echo "$name 포트 $port가 이미 사용 중입니다. 기존 프로세스를 그대로 둡니다."
    echo "필요하면 make dev-stop 후 다시 실행하세요."
    return
  fi

  nohup "$@" >"$log_file" 2>&1 &
  echo $! >"$pid_file"
  sleep 2

  if ! is_running "$pid_file"; then
    echo "$name 실행에 실패했습니다. 로그:"
    tail -n 40 "$log_file" || true
    rm -f "$pid_file"
    exit 1
  fi

  echo "$name 실행: PID $(cat "$pid_file")"
}

cd "$ROOT_DIR"

echo "MySQL을 시작합니다."
docker compose up -d mysql
wait_for_mysql

start_managed_process \
  "백엔드 API" \
  8000 \
  "$RUN_DIR/backend.pid" \
  "$LOG_DIR/backend.log" \
  python3 -m uvicorn quantmate_api.main:app --app-dir "$ROOT_DIR/backend/src" --reload --host 127.0.0.1 --port 8000

start_managed_process \
  "프론트엔드 웹" \
  5173 \
  "$RUN_DIR/frontend.pid" \
  "$LOG_DIR/frontend.log" \
  npm --prefix "$ROOT_DIR/frontend" run dev -- --host 127.0.0.1

echo
echo "QuantMate 실행 완료"
echo "- Web: http://127.0.0.1:5173"
echo "- API: http://127.0.0.1:8000"
echo "- 로그: make dev-logs"
echo "- 종료: make dev-stop"
