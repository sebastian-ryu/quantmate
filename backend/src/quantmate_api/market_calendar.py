from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from quantmate_api.market_data import market_timezone, normalize_market_code


US_MARKET_HOLIDAY_NAMES = {
    "new_year": "New Year's Day",
    "mlk": "Martin Luther King Jr. Day",
    "presidents": "Washington's Birthday",
    "good_friday": "Good Friday",
    "memorial": "Memorial Day",
    "juneteenth": "Juneteenth National Independence Day",
    "independence": "Independence Day",
    "labor": "Labor Day",
    "thanksgiving": "Thanksgiving Day",
    "christmas": "Christmas Day",
}


def market_calendar_range(
    *,
    market: str,
    start: date,
    end: date,
) -> dict[str, Any]:
    if end < start:
        raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")

    market_code = normalize_market_code(market)
    items = []
    current = start
    while current <= end:
        is_open, reason = market_day_status(market_code, current)
        items.append(
            {
                "date": current.isoformat(),
                "market": market_code,
                "is_open": is_open,
                "reason": reason,
            }
        )
        current += timedelta(days=1)

    return {
        "market": market_code,
        "timezone": market_timezone(market_code),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "open_days": sum(1 for item in items if item["is_open"]),
        "closed_days": sum(1 for item in items if not item["is_open"]),
        "items": items,
    }


def is_market_trading_day(market: str, day: date) -> bool:
    return market_day_status(market, day)[0]


def previous_market_trading_day(market: str, day: date) -> date:
    candidate = day
    while not is_market_trading_day(market, candidate):
        candidate -= timedelta(days=1)
    return candidate


def market_day_status(market: str, day: date) -> tuple[bool, str]:
    market_code = normalize_market_code(market)
    if day.weekday() >= 5:
        return False, "주말"

    if market_code == "US":
        holiday_name = us_market_holiday_name(day)
        if holiday_name:
            return False, holiday_name
        return True, "정규 거래일"

    # KRX 승인 전에는 한국 휴장일을 완전 계산하지 않는다. 주말만 확정적으로 제외한다.
    return True, "정규 거래일"


def us_market_holiday_name(day: date) -> str:
    holidays: dict[date, str] = {}
    for year in range(day.year - 1, day.year + 2):
        holidays.update(us_market_holidays(year))
    return holidays.get(day, "")


def us_market_holidays(year: int) -> dict[date, str]:
    return {
        observed_fixed_holiday(year, 1, 1): US_MARKET_HOLIDAY_NAMES["new_year"],
        nth_weekday_of_month(year, 1, 0, 3): US_MARKET_HOLIDAY_NAMES["mlk"],
        nth_weekday_of_month(year, 2, 0, 3): US_MARKET_HOLIDAY_NAMES["presidents"],
        easter_sunday(year) - timedelta(days=2): US_MARKET_HOLIDAY_NAMES["good_friday"],
        last_weekday_of_month(year, 5, 0): US_MARKET_HOLIDAY_NAMES["memorial"],
        observed_fixed_holiday(year, 6, 19): US_MARKET_HOLIDAY_NAMES["juneteenth"],
        observed_fixed_holiday(year, 7, 4): US_MARKET_HOLIDAY_NAMES["independence"],
        nth_weekday_of_month(year, 9, 0, 1): US_MARKET_HOLIDAY_NAMES["labor"],
        nth_weekday_of_month(year, 11, 3, 4): US_MARKET_HOLIDAY_NAMES["thanksgiving"],
        observed_fixed_holiday(year, 12, 25): US_MARKET_HOLIDAY_NAMES["christmas"],
    }


def observed_fixed_holiday(year: int, month: int, day: int) -> date:
    holiday = date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    candidate = date(year, month, 1)
    while candidate.weekday() != weekday:
        candidate += timedelta(days=1)
    return candidate + timedelta(days=7 * (n - 1))


def last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        candidate = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        candidate = date(year, month + 1, 1) - timedelta(days=1)

    while candidate.weekday() != weekday:
        candidate -= timedelta(days=1)
    return candidate


def easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    correction = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * correction) // 451
    month = (h + correction - 7 * m + 114) // 31
    day = ((h + correction - 7 * m + 114) % 31) + 1
    return date(year, month, day)
