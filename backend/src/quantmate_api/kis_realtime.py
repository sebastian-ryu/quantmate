from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import websockets

from quantmate_api.market_data import (
    float_from_kis,
    get_kis_environment_name,
    get_kis_ws_approval_key,
    get_kis_ws_url,
    int_from_kis,
    normalize_kis_symbol,
)
from quantmate_api.time_utils import now_kst_naive, today_kst


KIS_REALTIME_TRADE_TR_ID = "H0STCNT0"


@dataclass(frozen=True)
class KisRealtimeQuote:
    symbol: str
    trade_time: str
    price: int | None
    change: int | None
    change_rate: float | None
    trade_volume: int | None
    accumulated_volume: int | None
    accumulated_trading_value: int | None
    bid_price: int | None
    ask_price: int | None
    received_at: str
    raw_tr_id: str

    def as_response_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class KisRealtimeStatus:
    provider: str
    environment: str
    ws_url: str
    running: bool
    connected: bool
    subscribed_symbols: list[str]
    quote_count: int
    last_message_at: str | None
    last_error: str

    def as_response_row(self) -> dict[str, Any]:
        return asdict(self)


def max_realtime_symbols() -> int:
    value = os.getenv("KIS_REALTIME_MAX_SYMBOLS", "").strip()
    if not value:
        return 20
    try:
        return max(1, min(50, int(value)))
    except ValueError:
        return 20


def parse_kis_realtime_quote(raw_message: str) -> KisRealtimeQuote | None:
    parts = raw_message.split("|", 3)
    if len(parts) != 4:
        return None

    _, tr_id, _, payload = parts
    if tr_id != KIS_REALTIME_TRADE_TR_ID:
        return None

    fields = payload.split("^")
    if len(fields) < 15:
        return None

    symbol = fields[0].strip()
    if not symbol:
        return None

    trade_time = fields[1].strip()
    return KisRealtimeQuote(
        symbol=symbol,
        trade_time=format_kis_trade_time(trade_time),
        price=int_from_kis(fields[2]),
        change=int_from_kis(fields[4]),
        change_rate=float_from_kis(fields[5]),
        ask_price=int_from_kis(fields[10]),
        bid_price=int_from_kis(fields[11]),
        trade_volume=int_from_kis(fields[12]),
        accumulated_volume=int_from_kis(fields[13]),
        accumulated_trading_value=int_from_kis(fields[14]),
        received_at=now_kst_naive().isoformat(timespec="seconds"),
        raw_tr_id=tr_id,
    )


def format_kis_trade_time(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) != 6 or not cleaned.isdigit():
        return cleaned

    trade_date = today_kst()
    trade_datetime = datetime(
        trade_date.year,
        trade_date.month,
        trade_date.day,
        int(cleaned[:2]),
        int(cleaned[2:4]),
        int(cleaned[4:6]),
    )
    return trade_datetime.isoformat(timespec="seconds")


class KisRealtimeQuoteService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._websocket: Any | None = None
        self._subscribed_symbols: set[str] = set()
        self._latest_quotes: dict[str, KisRealtimeQuote] = {}
        self._connected = False
        self._last_message_at: str | None = None
        self._last_error = ""

    async def subscribe(self, symbols: list[str]) -> KisRealtimeStatus:
        normalized_symbols = normalize_realtime_symbols(symbols)
        if not normalized_symbols:
            raise ValueError("구독할 종목코드를 입력하세요.")

        async with self._lock:
            limit = max_realtime_symbols()
            merged_symbols = list(dict.fromkeys([*sorted(self._subscribed_symbols), *normalized_symbols]))
            if len(merged_symbols) > limit:
                raise ValueError(f"실시간 구독은 최대 {limit}개 종목까지 허용합니다.")

            new_symbols = [symbol for symbol in normalized_symbols if symbol not in self._subscribed_symbols]
            self._subscribed_symbols.update(normalized_symbols)
            self._ensure_task_locked()

            websocket = self._websocket

        if websocket is not None and self._connected:
            for symbol in new_symbols:
                await self._send_subscription(websocket, symbol, subscribe=True)

        return await self.status()

    async def unsubscribe(self, symbols: list[str]) -> KisRealtimeStatus:
        normalized_symbols = normalize_realtime_symbols(symbols)

        async with self._lock:
            target_symbols = [symbol for symbol in normalized_symbols if symbol in self._subscribed_symbols]
            for symbol in target_symbols:
                self._subscribed_symbols.discard(symbol)
            websocket = self._websocket

        if websocket is not None and self._connected:
            for symbol in target_symbols:
                await self._send_subscription(websocket, symbol, subscribe=False)

        return await self.status()

    async def stop(self) -> KisRealtimeStatus:
        async with self._lock:
            task = self._task
            self._task = None
            self._websocket = None
            self._connected = False
            self._subscribed_symbols.clear()

        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        return await self.status()

    async def status(self) -> KisRealtimeStatus:
        async with self._lock:
            running = self._task is not None and not self._task.done()
            return KisRealtimeStatus(
                provider="KIS Open API",
                environment=get_kis_environment_name(),
                ws_url=get_kis_ws_url(),
                running=running,
                connected=self._connected,
                subscribed_symbols=sorted(self._subscribed_symbols),
                quote_count=len(self._latest_quotes),
                last_message_at=self._last_message_at,
                last_error=self._last_error,
            )

    async def latest_quotes(self) -> list[KisRealtimeQuote]:
        async with self._lock:
            return sorted(self._latest_quotes.values(), key=lambda quote: quote.symbol)

    def _ensure_task_locked(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="kis-realtime-quotes")

    async def _run(self) -> None:
        while True:
            async with self._lock:
                symbols = sorted(self._subscribed_symbols)

            if not symbols:
                async with self._lock:
                    self._connected = False
                    self._websocket = None
                return

            try:
                approval_key = await asyncio.to_thread(get_kis_ws_approval_key)
                ws_url = get_kis_ws_url()
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as websocket:
                    async with self._lock:
                        self._websocket = websocket
                        self._connected = True
                        self._last_error = ""

                    for symbol in symbols:
                        await self._send_subscription(websocket, symbol, subscribe=True, approval_key=approval_key)

                    async for raw_message in websocket:
                        await self._handle_raw_message(websocket, str(raw_message))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                async with self._lock:
                    self._connected = False
                    self._websocket = None
                    self._last_error = str(exc)
                await asyncio.sleep(3)

    async def _send_subscription(
        self,
        websocket: Any,
        symbol: str,
        *,
        subscribe: bool,
        approval_key: str | None = None,
    ) -> None:
        effective_approval_key = approval_key or await asyncio.to_thread(get_kis_ws_approval_key)
        payload = {
            "header": {
                "approval_key": effective_approval_key,
                "custtype": "P",
                "tr_type": "1" if subscribe else "2",
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": KIS_REALTIME_TRADE_TR_ID,
                    "tr_key": symbol,
                }
            },
        }
        await websocket.send(json.dumps(payload, ensure_ascii=False))

    async def _handle_raw_message(self, websocket: Any, raw_message: str) -> None:
        if raw_message.startswith("{"):
            await self._handle_control_message(websocket, raw_message)
            return

        quote = parse_kis_realtime_quote(raw_message)
        if quote is None:
            return

        async with self._lock:
            self._latest_quotes[quote.symbol] = quote
            self._last_message_at = quote.received_at

    async def _handle_control_message(self, websocket: Any, raw_message: str) -> None:
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            return

        header = payload.get("header") if isinstance(payload, dict) else None
        tr_id = str(header.get("tr_id") or "") if isinstance(header, dict) else ""
        if tr_id.upper() == "PINGPONG":
            await websocket.send(raw_message)


def normalize_realtime_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    for symbol in symbols:
        try:
            normalized_symbol = normalize_kis_symbol(symbol)
        except ValueError as exc:
            raise ValueError("종목코드를 확인하세요.") from exc

        if normalized_symbol not in normalized:
            normalized.append(normalized_symbol)

    return normalized


kis_realtime_quote_service = KisRealtimeQuoteService()
