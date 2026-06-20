#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

stop_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    return
  fi

  local pid
  pid="$(cat "$pid_file")"

  if kill -0 "$pid" 2>/dev/null; then
    echo "$name 종료: PID $pid"
    kill "$pid" 2>/dev/null || true

    for _ in {1..20}; do
      if ! kill -0 "$pid" 2>/dev/null; then
        break
      fi
      sleep 0.2
    done

    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi

  rm -f "$pid_file"
}

stop_port() {
  local name="$1"
  local port="$2"

  if ! command -v lsof >/dev/null 2>&1; then
    return
  fi

  local pids
  pids="$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null || true)"

  if [[ -z "$pids" ]]; then
    return
  fi

  echo "$name 포트 $port 사용 프로세스 종료: $pids"
  for pid in $pids; do
    kill "$pid" 2>/dev/null || true
  done
}

cd "$ROOT_DIR"

stop_pid_file "백엔드 API" "$RUN_DIR/backend.pid"
stop_pid_file "프론트엔드 웹" "$RUN_DIR/frontend.pid"

stop_port "백엔드 API" 8000
stop_port "프론트엔드 웹" 5173

echo "MySQL을 종료합니다."
if command -v docker >/dev/null 2>&1; then
  docker compose down || echo "Docker 종료 확인 중 오류가 있었지만 서버 종료는 계속 진행했습니다."
else
  echo "Docker 명령을 찾지 못해 MySQL 종료를 건너뜁니다."
fi

echo "QuantMate 종료 완료"
