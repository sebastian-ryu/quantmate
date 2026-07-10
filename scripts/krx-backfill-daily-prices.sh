#!/bin/sh

set -u

API_BASE_URL="${BACKFILL_API_BASE_URL:-${PUBLIC_API_BASE_URL:-http://127.0.0.1:8000}}"
START_YEAR="${BACKFILL_START_YEAR:-2010}"
END_YEAR="${BACKFILL_END_YEAR:-$(date +%Y)}"
START_DATE_OVERRIDE="${BACKFILL_START_DATE:-}"
END_DATE_OVERRIDE="${BACKFILL_END_DATE:-}"
MARKETS_RAW="${BACKFILL_MARKETS:-KOSPI KOSDAQ}"
SLEEP_SECONDS="${BACKFILL_SLEEP_SECONDS:-1}"
IMPORT_INSTRUMENTS="${BACKFILL_IMPORT_INSTRUMENTS:-true}"
CONTINUE_ON_ERROR="${BACKFILL_CONTINUE_ON_ERROR:-false}"
DRY_RUN="${BACKFILL_DRY_RUN:-false}"
LOG_DIR="${BACKFILL_LOG_DIR:-./runtime/logs/backfill}"
REQUEST_TIMEOUT_SECONDS="${BACKFILL_REQUEST_TIMEOUT_SECONDS:-1800}"

case "$START_YEAR" in
  *[!0-9]* | "") echo "BACKFILL_START_YEAR는 숫자여야 합니다: $START_YEAR" >&2; exit 2 ;;
esac

case "$END_YEAR" in
  *[!0-9]* | "") echo "BACKFILL_END_YEAR는 숫자여야 합니다: $END_YEAR" >&2; exit 2 ;;
esac

if [ "$START_YEAR" -gt "$END_YEAR" ]; then
  echo "시작 연도는 종료 연도보다 클 수 없습니다: $START_YEAR > $END_YEAR" >&2
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl 명령을 찾을 수 없습니다. NAS 패키지 또는 기본 셸 환경을 확인해 주세요." >&2
  exit 2
fi

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/krx-backfill-$(date +%Y%m%d-%H%M%S).log"
MARKETS=$(printf "%s" "$MARKETS_RAW" | tr "," " ")

log() {
  printf "%s %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

post_json() {
  endpoint="$1"
  payload="$2"
  tmp_file="${TMPDIR:-/tmp}/quantmate-backfill-response-$$.json"

  if [ "$DRY_RUN" = "true" ]; then
    log "DRY_RUN POST $endpoint $payload"
    return 0
  fi

  http_code=$(
    curl -sS \
      --max-time "$REQUEST_TIMEOUT_SECONDS" \
      -o "$tmp_file" \
      -w "%{http_code}" \
      -X POST "$API_BASE_URL$endpoint" \
      -H "Content-Type: application/json" \
      -d "$payload"
  )
  curl_exit=$?

  if [ "$curl_exit" -ne 0 ]; then
    log "실패: curl 오류 코드 $curl_exit · $endpoint"
    rm -f "$tmp_file"
    return 1
  fi

  response_body=$(cat "$tmp_file")
  rm -f "$tmp_file"

  case "$http_code" in
    200 | 201 | 202)
      log "성공: HTTP $http_code · $response_body"
      return 0
      ;;
    *)
      log "실패: HTTP $http_code · $response_body"
      return 1
      ;;
  esac
}

run_step() {
  label="$1"
  endpoint="$2"
  payload="$3"

  log "시작: $label"
  if post_json "$endpoint" "$payload"; then
    log "완료: $label"
    return 0
  fi

  log "오류: $label"
  if [ "$CONTINUE_ON_ERROR" = "true" ]; then
    return 0
  fi
  return 1
}

log "KRX 장기 일봉 적재 시작"
log "API_BASE_URL=$API_BASE_URL"
log "기간=${START_YEAR}년~${END_YEAR}년, 시장=$MARKETS, 로그=$LOG_FILE"

if [ "$IMPORT_INSTRUMENTS" = "true" ]; then
  run_step \
    "KRX 종목 마스터 갱신" \
    "/api/data/krx/instruments/import" \
    "{\"market\":\"ALL\",\"limit\":3000}" || exit 1
fi

year="$START_YEAR"
while [ "$year" -le "$END_YEAR" ]; do
  start_date="$year-01-01"
  end_date="$year-12-31"

  if [ -n "$START_DATE_OVERRIDE" ] && [ "$year" -eq "$START_YEAR" ]; then
    start_date="$START_DATE_OVERRIDE"
  fi

  if [ -n "$END_DATE_OVERRIDE" ] && [ "$year" -eq "$END_YEAR" ]; then
    end_date="$END_DATE_OVERRIDE"
  elif [ "$year" -eq "$(date +%Y)" ]; then
    end_date="$(date +%Y-%m-%d)"
  fi

  for market in $MARKETS; do
    payload="{\"market\":\"$market\",\"start\":\"$start_date\",\"end\":\"$end_date\"}"
    run_step \
      "KRX $market 일봉 적재 $start_date~$end_date" \
      "/api/data/krx/daily-prices/import/market" \
      "$payload" || exit 1

    if [ "$SLEEP_SECONDS" != "0" ]; then
      sleep "$SLEEP_SECONDS"
    fi
  done

  year=$((year + 1))
done

log "KRX 장기 일봉 적재 완료"
