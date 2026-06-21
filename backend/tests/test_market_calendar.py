from datetime import date

from quantmate_api.market_calendar import (
    is_market_trading_day,
    market_calendar_range,
    previous_market_trading_day,
    us_market_holiday_name,
)


def test_us_market_calendar_closes_on_2026_nyse_holidays() -> None:
    assert us_market_holiday_name(date(2026, 1, 1)) == "New Year's Day"
    assert us_market_holiday_name(date(2026, 4, 3)) == "Good Friday"
    assert us_market_holiday_name(date(2026, 6, 19)) == "Juneteenth National Independence Day"
    assert us_market_holiday_name(date(2026, 7, 3)) == "Independence Day"
    assert us_market_holiday_name(date(2026, 11, 26)) == "Thanksgiving Day"


def test_us_market_trading_day_status() -> None:
    assert is_market_trading_day("US", date(2026, 6, 19)) is False
    assert is_market_trading_day("US", date(2026, 6, 22)) is True
    assert previous_market_trading_day("US", date(2026, 6, 21)) == date(2026, 6, 18)


def test_market_calendar_range_counts_open_and_closed_days() -> None:
    payload = market_calendar_range(
        market="NASDAQ",
        start=date(2026, 6, 18),
        end=date(2026, 6, 22),
    )

    assert payload["market"] == "US"
    assert payload["timezone"] == "America/New_York"
    assert payload["open_days"] == 2
    assert payload["closed_days"] == 3
    assert [item["is_open"] for item in payload["items"]] == [True, False, False, False, True]
