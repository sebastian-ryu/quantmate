#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta


API_BASE_URL = os.getenv("ENRICHMENT_API_BASE_URL") or os.getenv("BACKFILL_API_BASE_URL") or "http://127.0.0.1:8000"
MARKETS = [item.strip().upper() for item in os.getenv("ENRICHMENT_MARKETS", "KOSPI KOSDAQ").replace(",", " ").split()]
PAGE_SIZE = max(1, min(int(os.getenv("ENRICHMENT_PAGE_SIZE", "200")), 500))
SYMBOL_LIMIT = max(0, int(os.getenv("ENRICHMENT_SYMBOL_LIMIT", "0")))
REQUEST_TIMEOUT_SECONDS = max(5, int(os.getenv("ENRICHMENT_REQUEST_TIMEOUT_SECONDS", "1800")))
INSTRUMENT_REQUEST_TIMEOUT_SECONDS = max(5, int(os.getenv("ENRICHMENT_INSTRUMENT_REQUEST_TIMEOUT_SECONDS", "60")))
SLEEP_SECONDS = float(os.getenv("ENRICHMENT_SLEEP_SECONDS", "0.2"))
CONTINUE_ON_ERROR = os.getenv("ENRICHMENT_CONTINUE_ON_ERROR", "true").lower() == "true"
FORCE_UPDATE = os.getenv("ENRICHMENT_FORCE_UPDATE", "false").lower() == "true"
SKIP_MIN_RATIO = float(os.getenv("ENRICHMENT_SKIP_MIN_RATIO", "0.8"))
DRY_RUN = os.getenv("ENRICHMENT_DRY_RUN", "false").lower() == "true"
DRY_RUN_SYMBOLS = max(0, int(os.getenv("ENRICHMENT_DRY_RUN_SYMBOLS", "0")))
INCLUDE_STATIC = os.getenv("ENRICHMENT_INCLUDE_STATIC", "true").lower() == "true"
INCLUDE_QUOTE = os.getenv("ENRICHMENT_INCLUDE_QUOTE", "true").lower() == "true"
INCLUDE_KIS_FUNDAMENTALS = os.getenv("ENRICHMENT_INCLUDE_KIS_FUNDAMENTALS", "true").lower() == "true"
INCLUDE_OPEN_DART = os.getenv("ENRICHMENT_INCLUDE_OPEN_DART", "true").lower() == "true"
INCLUDE_MONTHLY = os.getenv("ENRICHMENT_INCLUDE_MONTHLY", "true").lower() == "true"
INCLUDE_SUPPLY_FLOW = os.getenv("ENRICHMENT_INCLUDE_SUPPLY_FLOW", "true").lower() == "true"
INCLUDE_RISK_INDICATORS = os.getenv("ENRICHMENT_INCLUDE_RISK_INDICATORS", "true").lower() == "true"


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    exchange: str


@dataclass(frozen=True)
class MonthChunk:
    start: date
    end: date


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def today() -> date:
    return date.today()


def default_start_date() -> date:
    return today() - timedelta(days=365)


START_DATE = parse_date(os.getenv("ENRICHMENT_START_DATE", default_start_date().isoformat()))
END_DATE = parse_date(os.getenv("ENRICHMENT_END_DATE", today().isoformat()))


def month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, month, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def month_chunks(start: date, end: date) -> list[MonthChunk]:
    if end < start:
        raise SystemExit(f"종료일은 시작일보다 빠를 수 없습니다: {start} > {end}")

    chunks: list[MonthChunk] = []
    current = date(start.year, start.month, 1)
    while current <= end:
        chunk_start = max(current, start)
        chunk_end = min(month_end(current.year, current.month), end)
        chunks.append(MonthChunk(start=chunk_start, end=chunk_end))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return chunks


def request_json(
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
    *,
    timeout_seconds: int | None = None,
) -> dict[str, object]:
    url = f"{API_BASE_URL}{path}"
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if DRY_RUN:
        print(f"DRY_RUN {method} {url} {json.dumps(payload, ensure_ascii=False) if payload else ''}")
        if path == "/api/data/enrichment/coverage":
            return {"complete": False, "missing_parts": ["DRY_RUN"]}
        return {}

    request = urllib.request.Request(url=url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds or REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} · {raw}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"연결 실패 · {exc.reason}") from exc


def get_instruments_for_market(market: str) -> list[Instrument]:
    instruments: list[Instrument] = []
    offset = 0
    while True:
        params = urllib.parse.urlencode({"market": market, "limit": PAGE_SIZE, "offset": offset})
        print(f"종목 목록 조회 중: {market} offset={offset} limit={PAGE_SIZE}", flush=True)
        data = request_json(
            "GET",
            f"/api/data/instruments/local?{params}",
            timeout_seconds=INSTRUMENT_REQUEST_TIMEOUT_SECONDS,
        )
        if DRY_RUN:
            return []

        items = data.get("items") or []
        for item in items:
            instruments.append(
                Instrument(
                    symbol=str(item["symbol"]),
                    name=str(item["name"]),
                    exchange=str(item["exchange"]),
                )
            )

        if len(items) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return instruments


def load_instruments() -> list[Instrument]:
    if DRY_RUN and DRY_RUN_SYMBOLS:
        return [
            Instrument(symbol=f"TEST{index:03d}", name=f"테스트종목{index:03d}", exchange="KOSPI")
            for index in range(1, DRY_RUN_SYMBOLS + 1)
        ]

    merged: dict[str, Instrument] = {}
    for market in MARKETS:
        for instrument in get_instruments_for_market(market):
            merged[instrument.symbol] = instrument
    instruments = sorted(merged.values(), key=lambda item: (item.exchange, item.symbol))
    return instruments[:SYMBOL_LIMIT] if SYMBOL_LIMIT else instruments


def business_years() -> list[int] | None:
    raw_value = os.getenv("ENRICHMENT_OPEN_DART_YEARS", "").strip()
    if not raw_value:
        return None
    return [int(item.strip()) for item in raw_value.replace(",", " ").split() if item.strip()]


def enrichment_payload(
    instrument: Instrument,
    start: date,
    end: date,
    *,
    static: bool,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "symbol": instrument.symbol,
        "name": instrument.name,
        "exchange": instrument.exchange,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "include_quote": static and INCLUDE_QUOTE,
        "include_kis_fundamentals": static and INCLUDE_KIS_FUNDAMENTALS,
        "include_open_dart": static and INCLUDE_OPEN_DART,
        "include_supply_flow": (not static) and INCLUDE_SUPPLY_FLOW,
        "include_risk_indicators": (not static) and INCLUDE_RISK_INDICATORS,
    }
    years = business_years()
    if years:
        payload["open_dart_business_years"] = years
    return payload


def coverage_payload(
    instrument: Instrument,
    start: date,
    end: date,
    *,
    static: bool,
) -> dict[str, object]:
    payload = enrichment_payload(instrument, start, end, static=static)
    payload["min_ratio"] = SKIP_MIN_RATIO
    return payload


def print_step(index: int, total: int, message: str) -> float:
    pct = int(index * 100 / total) if total else 0
    started_at = time.monotonic()
    print(f"[{index}/{total} {pct}%] 시작: {message}", flush=True)
    return started_at


def print_done(index: int, total: int, message: str, started_at: float) -> None:
    pct = int(index * 100 / total) if total else 0
    elapsed = int(time.monotonic() - started_at)
    print(f"[{index}/{total} {pct}%] 완료: {message} · 소요 {elapsed}초", flush=True)


def print_error(index: int, total: int, message: str, started_at: float, error: Exception) -> None:
    pct = int(index * 100 / total) if total else 0
    elapsed = int(time.monotonic() - started_at)
    print(f"[{index}/{total} {pct}%] 오류: {message} · 소요 {elapsed}초 · {error}", flush=True)


def print_skip(index: int, total: int, message: str, reason: str) -> None:
    pct = int(index * 100 / total) if total else 0
    print(f"[{index}/{total} {pct}%] 스킵: {message} · {reason}", flush=True)


def coverage_is_complete(payload: dict[str, object]) -> tuple[bool, str]:
    if FORCE_UPDATE:
        return False, "강제 갱신"

    try:
        response = request_json("POST", "/api/data/enrichment/coverage", payload)
    except Exception as exc:  # noqa: BLE001 - CLI should proceed when coverage check itself fails.
        return False, f"커버리지 확인 실패: {exc}"

    if not response.get("complete"):
        missing_parts = response.get("missing_parts") or []
        missing_text = ", ".join(str(item) for item in missing_parts) if missing_parts else "부족 데이터 있음"
        return False, missing_text

    supply_ratio = response.get("supply_flow_coverage_ratio")
    risk_ratio = response.get("risk_indicator_coverage_ratio")
    stored_years = response.get("open_dart_stored_years") or []
    reason_parts = ["이미 적재됨"]
    if supply_ratio is not None:
        reason_parts.append(f"수급 {supply_ratio}")
    if risk_ratio is not None:
        reason_parts.append(f"리스크 {risk_ratio}")
    if stored_years:
        reason_parts.append(f"OpenDART {stored_years}")
    return True, " · ".join(reason_parts)


def run_step(index: int, total: int, label: str, payload: dict[str, object]) -> str | None:
    started_at = print_step(index, total, label)
    try:
        response = request_json("POST", "/api/data/enrichment/import", payload)
        warnings = response.get("warnings") or []
        if warnings:
            print(f"[{index}/{total}] 경고: {' | '.join(str(item) for item in warnings)}", flush=True)
        print_done(index, total, label, started_at)
        return None
    except Exception as exc:  # noqa: BLE001 - CLI must summarize failures without hiding the step.
        print_error(index, total, label, started_at, exc)
        if not CONTINUE_ON_ERROR:
            raise
        return f"{label} · {exc}"
    finally:
        if SLEEP_SECONDS > 0:
            time.sleep(SLEEP_SECONDS)


def main() -> int:
    print("초기 보조 데이터 적재 준비", flush=True)
    print(f"API_BASE_URL={API_BASE_URL}", flush=True)
    print(f"시장={' '.join(MARKETS)}, 기간={START_DATE}~{END_DATE}, 종목 제한={SYMBOL_LIMIT or '전체'}", flush=True)
    print("종목 목록 조회 시작", flush=True)
    chunks = month_chunks(START_DATE, END_DATE)
    instruments = load_instruments()
    print(f"종목 목록 조회 완료: {len(instruments)}개", flush=True)
    static_steps = len(instruments) if INCLUDE_STATIC and (INCLUDE_QUOTE or INCLUDE_KIS_FUNDAMENTALS or INCLUDE_OPEN_DART) else 0
    monthly_steps = (
        len(instruments) * len(chunks)
        if INCLUDE_MONTHLY and (INCLUDE_SUPPLY_FLOW or INCLUDE_RISK_INDICATORS)
        else 0
    )
    total_steps = static_steps + monthly_steps
    failures: list[str] = []
    skipped_count = 0

    print("초기 보조 데이터 적재 시작", flush=True)
    print(f"시장={' '.join(MARKETS)}, 종목={len(instruments)}개, 기간={START_DATE}~{END_DATE}", flush=True)
    print(f"실행 단위=정적 종목 청크 + 월별 종목 청크, 전체 단계={total_steps}", flush=True)
    print(f"스킵 기준: FORCE_UPDATE={str(FORCE_UPDATE).lower()}, SKIP_MIN_RATIO={SKIP_MIN_RATIO}", flush=True)

    if total_steps == 0:
        print("실행할 단계가 없습니다. 종목 마스터가 비어 있거나 포함 옵션이 모두 꺼져 있습니다.", flush=True)
        return 0

    step_index = 0
    if static_steps:
        for instrument in instruments:
            step_index += 1
            label = f"{instrument.symbol} {instrument.name} 정적 보조 데이터"
            complete, reason = coverage_is_complete(
                coverage_payload(instrument, END_DATE, END_DATE, static=True)
            )
            if complete:
                skipped_count += 1
                print_skip(step_index, total_steps, label, reason)
                continue
            failure = run_step(
                step_index,
                total_steps,
                label,
                enrichment_payload(instrument, END_DATE, END_DATE, static=True),
            )
            if failure:
                failures.append(failure)

    if monthly_steps:
        for chunk in chunks:
            for instrument in instruments:
                step_index += 1
                label = f"{instrument.symbol} {instrument.name} 월별 수급/리스크 {chunk.start}~{chunk.end}"
                complete, reason = coverage_is_complete(
                    coverage_payload(instrument, chunk.start, chunk.end, static=False)
                )
                if complete:
                    skipped_count += 1
                    print_skip(step_index, total_steps, label, reason)
                    continue
                failure = run_step(
                    step_index,
                    total_steps,
                    label,
                    enrichment_payload(instrument, chunk.start, chunk.end, static=False),
                )
                if failure:
                    failures.append(failure)

    print(f"초기 보조 데이터 적재 완료 · 처리 단계 {step_index}/{total_steps} · 스킵 {skipped_count}건", flush=True)
    if failures:
        print(f"실패 구간 {len(failures)}건", flush=True)
        for failure in failures:
            print(f"- {failure}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
