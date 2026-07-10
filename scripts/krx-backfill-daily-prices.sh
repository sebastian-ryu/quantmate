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
FORCE_UPDATE="${BACKFILL_FORCE_UPDATE:-false}"
SKIP_MIN_RATIO="${BACKFILL_SKIP_MIN_RATIO:-0.9}"
DRY_RUN="${BACKFILL_DRY_RUN:-false}"
LOG_DIR="${BACKFILL_LOG_DIR:-./runtime/logs/backfill}"
REQUEST_TIMEOUT_SECONDS="${BACKFILL_REQUEST_TIMEOUT_SECONDS:-1800}"
LAST_RESPONSE_BODY=""
LAST_HTTP_CODE=""

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
CURRENT_YEAR="$(date +%Y)"
TODAY="$(date +%Y-%m-%d)"

if [ -n "$START_DATE_OVERRIDE" ]; then
  EFFECTIVE_START_DATE="$START_DATE_OVERRIDE"
else
  EFFECTIVE_START_DATE="$START_YEAR-01-01"
fi

if [ -n "$END_DATE_OVERRIDE" ]; then
  EFFECTIVE_END_DATE="$END_DATE_OVERRIDE"
elif [ "$END_YEAR" -eq "$CURRENT_YEAR" ]; then
  EFFECTIVE_END_DATE="$TODAY"
else
  EFFECTIVE_END_DATE="$END_YEAR-12-31"
fi

TOTAL_STEPS=0
CURRENT_STEP=0
STEP_STARTED_AT=0
COVERAGE_SUMMARY=""

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
  LAST_RESPONSE_BODY="$response_body"
  LAST_HTTP_CODE="$http_code"

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

get_json() {
  endpoint="$1"
  tmp_file="${TMPDIR:-/tmp}/quantmate-backfill-response-$$.json"

  if [ "$DRY_RUN" = "true" ]; then
    LAST_RESPONSE_BODY='{"complete":false,"coverage_ratio":0,"stored_trade_dates":0,"expected_weekdays":0,"stored_rows":0}'
    LAST_HTTP_CODE="200"
    log "DRY_RUN GET $endpoint"
    return 0
  fi

  http_code=$(
    curl -sS \
      --max-time "$REQUEST_TIMEOUT_SECONDS" \
      -o "$tmp_file" \
      -w "%{http_code}" \
      "$API_BASE_URL$endpoint"
  )
  curl_exit=$?

  if [ "$curl_exit" -ne 0 ]; then
    log "커버리지 확인 실패: curl 오류 코드 $curl_exit · $endpoint"
    rm -f "$tmp_file"
    return 1
  fi

  LAST_RESPONSE_BODY=$(cat "$tmp_file")
  LAST_HTTP_CODE="$http_code"
  rm -f "$tmp_file"

  case "$http_code" in
    200) return 0 ;;
    *)
      log "커버리지 확인 실패: HTTP $http_code · $LAST_RESPONSE_BODY"
      return 1
      ;;
  esac
}

json_field() {
  field="$1"
  printf "%s" "$LAST_RESPONSE_BODY" | sed -n "s/.*\"$field\":[[:space:]]*\"\{0,1\}\([^,}\"]*\)\"\{0,1\}.*/\1/p"
}

is_leap_year() {
  year_value="$1"
  if [ $((year_value % 400)) -eq 0 ]; then
    return 0
  fi
  if [ $((year_value % 4)) -eq 0 ] && [ $((year_value % 100)) -ne 0 ]; then
    return 0
  fi
  return 1
}

month_last_day() {
  year_value="$1"
  month_value="$2"

  case "$month_value" in
    1 | 3 | 5 | 7 | 8 | 10 | 12) echo "31" ;;
    4 | 6 | 9 | 11) echo "30" ;;
    2)
      if is_leap_year "$year_value"; then
        echo "29"
      else
        echo "28"
      fi
      ;;
  esac
}

date_before() {
  [ "$1" \< "$2" ]
}

date_after() {
  [ "$1" \> "$2" ]
}

max_date() {
  if date_before "$1" "$2"; then
    printf "%s" "$2"
  else
    printf "%s" "$1"
  fi
}

min_date() {
  if date_after "$1" "$2"; then
    printf "%s" "$2"
  else
    printf "%s" "$1"
  fi
}

count_month_market_steps() {
  count=0
  year_value="$START_YEAR"
  while [ "$year_value" -le "$END_YEAR" ]; do
    month_value=1
    while [ "$month_value" -le 12 ]; do
      month_start=$(printf "%04d-%02d-01" "$year_value" "$month_value")
      month_end=$(printf "%04d-%02d-%02d" "$year_value" "$month_value" "$(month_last_day "$year_value" "$month_value")")

      if ! date_before "$month_end" "$EFFECTIVE_START_DATE" && ! date_after "$month_start" "$EFFECTIVE_END_DATE"; then
        for _market in $MARKETS; do
          count=$((count + 1))
        done
      fi

      month_value=$((month_value + 1))
    done
    year_value=$((year_value + 1))
  done

  if [ "$IMPORT_INSTRUMENTS" = "true" ]; then
    count=$((count + 1))
  fi

  echo "$count"
}

step_prefix() {
  if [ "$TOTAL_STEPS" -le 0 ]; then
    printf "[0/0 0%%]"
    return
  fi

  pct=$((CURRENT_STEP * 100 / TOTAL_STEPS))
  printf "[%s/%s %s%%]" "$CURRENT_STEP" "$TOTAL_STEPS" "$pct"
}

begin_step() {
  CURRENT_STEP=$((CURRENT_STEP + 1))
  STEP_STARTED_AT=$(date +%s)
  log "$(step_prefix) 시작: $1"
}

finish_step() {
  label="$1"
  result="$2"
  elapsed=$(( $(date +%s) - STEP_STARTED_AT ))
  log "$(step_prefix) $result: $label · 소요 ${elapsed}초"
}

skip_step() {
  label="$1"
  reason="$2"
  CURRENT_STEP=$((CURRENT_STEP + 1))
  log "$(step_prefix) 스킵: $label · $reason"
}

coverage_is_complete() {
  market="$1"
  start_date="$2"
  end_date="$3"
  COVERAGE_SUMMARY=""

  if [ "$FORCE_UPDATE" = "true" ]; then
    return 1
  fi

  endpoint="/api/data/krx/daily-prices/coverage?market=$market&start=$start_date&end=$end_date&min_ratio=$SKIP_MIN_RATIO"
  if ! get_json "$endpoint"; then
    log "커버리지 확인을 할 수 없어 안전하게 적재를 진행합니다."
    return 1
  fi

  complete="$(json_field complete)"
  coverage_ratio="$(json_field coverage_ratio)"
  stored_trade_dates="$(json_field stored_trade_dates)"
  expected_weekdays="$(json_field expected_weekdays)"
  stored_rows="$(json_field stored_rows)"
  COVERAGE_SUMMARY="거래일 ${stored_trade_dates:-0}/${expected_weekdays:-0} · rows ${stored_rows:-0} · coverage ${coverage_ratio:-0}"

  if [ "$complete" = "true" ]; then
    return 0
  fi

  log "적재 필요: KRX $market $start_date~$end_date · $COVERAGE_SUMMARY"
  return 1
}

run_step() {
  label="$1"
  endpoint="$2"
  payload="$3"

  begin_step "$label"
  if post_json "$endpoint" "$payload"; then
    finish_step "$label" "완료"
    return 0
  fi

  finish_step "$label" "오류"
  if [ "$CONTINUE_ON_ERROR" = "true" ]; then
    return 0
  fi
  return 1
}

TOTAL_STEPS="$(count_month_market_steps)"

log "KRX 장기 일봉 적재 시작"
log "API_BASE_URL=$API_BASE_URL"
log "기간=$EFFECTIVE_START_DATE~$EFFECTIVE_END_DATE, 시장=$MARKETS, 로그=$LOG_FILE"
log "skip 기준: FORCE_UPDATE=$FORCE_UPDATE, SKIP_MIN_RATIO=$SKIP_MIN_RATIO"
log "실행 단위=월별 시장 청크, 전체 단계=$TOTAL_STEPS"

if [ "$IMPORT_INSTRUMENTS" = "true" ]; then
  run_step \
    "KRX 종목 마스터 갱신" \
    "/api/data/krx/instruments/import" \
    "{\"market\":\"ALL\",\"limit\":3000}" || exit 1
fi

year="$START_YEAR"
while [ "$year" -le "$END_YEAR" ]; do
  month=1
  while [ "$month" -le 12 ]; do
    month_start=$(printf "%04d-%02d-01" "$year" "$month")
    month_end=$(printf "%04d-%02d-%02d" "$year" "$month" "$(month_last_day "$year" "$month")")

    if date_before "$month_end" "$EFFECTIVE_START_DATE" || date_after "$month_start" "$EFFECTIVE_END_DATE"; then
      month=$((month + 1))
      continue
    fi

    start_date="$(max_date "$month_start" "$EFFECTIVE_START_DATE")"
    end_date="$(min_date "$month_end" "$EFFECTIVE_END_DATE")"

    for market in $MARKETS; do
      label="KRX $market 일봉 적재 $start_date~$end_date"
      if coverage_is_complete "$market" "$start_date" "$end_date"; then
        skip_step "$label" "$COVERAGE_SUMMARY"
        continue
      fi

      payload="{\"market\":\"$market\",\"start\":\"$start_date\",\"end\":\"$end_date\"}"
      run_step \
        "$label" \
        "/api/data/krx/daily-prices/import/market" \
        "$payload" || exit 1

      if [ "$SLEEP_SECONDS" != "0" ]; then
        sleep "$SLEEP_SECONDS"
      fi
    done

    month=$((month + 1))
  done

  year=$((year + 1))
done

log "KRX 장기 일봉 적재 완료 · 처리 단계 $CURRENT_STEP/$TOTAL_STEPS · 로그=$LOG_FILE"
