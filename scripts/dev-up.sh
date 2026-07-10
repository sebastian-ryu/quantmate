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

start_mysql() {
  echo "MySQL을 시작합니다."
  if docker compose up -d mysql; then
    wait_for_mysql
    return
  fi

  if port_in_use 3306; then
    echo "Docker MySQL 시작 확인은 실패했지만 3306 포트가 열려 있어 기존 MySQL을 사용합니다."
    return
  fi

  echo "MySQL을 시작하지 못했습니다. Docker 권한 또는 MySQL 실행 상태를 확인하세요."
  exit 1
}

load_public_env_from_dotenv() {
  local env_file="$ROOT_DIR/.env"
  [[ -f "$env_file" ]] || return

  while IFS='=' read -r key value; do
    [[ "$key" =~ ^PUBLIC_[A-Za-z0-9_]*$ ]] || continue
    value="${value%$'\r'}"

    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi

    export "$key=$value"
  done < "$env_file"
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
    echo "$name 포트 ${port}가 이미 사용 중입니다. 기존 프로세스를 그대로 둡니다."
    echo "필요하면 make dev-stop 후 다시 실행하세요."
    return
  fi

  python3 - "$pid_file" "$log_file" "$@" <<'PY'
import os
import subprocess
import sys

pid_file, log_file, *command = sys.argv[1:]
os.makedirs(os.path.dirname(log_file), exist_ok=True)

with open(log_file, "ab", buffering=0) as log:
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )

with open(pid_file, "w", encoding="utf-8") as file:
    file.write(str(process.pid))
PY
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

start_mysql

echo "DB 마이그레이션을 적용합니다."
python3 -m alembic -c "$ROOT_DIR/backend/alembic.ini" upgrade head

start_managed_process \
  "백엔드 API" \
  8000 \
  "$RUN_DIR/backend.pid" \
  "$LOG_DIR/backend.log" \
  python3 -m uvicorn quantmate_api.main:app --app-dir "$ROOT_DIR/backend/src" --host 127.0.0.1 --port 8000

load_public_env_from_dotenv

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
