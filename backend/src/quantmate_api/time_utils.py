from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo


KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    return datetime.now(KOREA_TIMEZONE)


def now_kst_naive() -> datetime:
    return now_kst().replace(tzinfo=None)


def today_kst() -> date:
    return now_kst().date()


def start_of_day_kst(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=KOREA_TIMEZONE)


def date_from_timestamp_kst(timestamp: int | float) -> date:
    return datetime.fromtimestamp(timestamp, KOREA_TIMEZONE).date()
