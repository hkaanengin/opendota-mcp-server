"""Everyday date windows ("last 30 days", "this month") → OpenDota's `date` (days back)."""

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastmcp.exceptions import ToolError

DAY = 86400
UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}
_RELATIVE = re.compile(r"(?:(?:last|past|previous)\s+)?(\d+)?\s*(day|week|month|year)s?")
_CALENDAR = re.compile(r"this\s+(week|month|year)")


@dataclass(frozen=True)
class DateWindow:
    days: int
    """OpenDota counts matches that started within this many days of now."""
    label: str


def resolve_date_window(value: str | int, now: float) -> DateWindow:
    """A number of days, "last N days/weeks/months/years", "today" or "this week/month/year".

    A calendar window is rounded up to whole days so repeated questions share a cache entry;
    it can reach up to a day before the period started.
    """
    text = re.sub(r"\s+", " ", str(value).strip().lower())
    if text.isdigit() and int(text) > 0:
        return _last(int(text))
    if text == "today":
        return _last(1)
    if match := _CALENDAR.fullmatch(text):
        unit = match[1]
        days = math.ceil((now - _period_start(unit, now).timestamp()) / DAY) or 1
        return DateWindow(days, f"this {unit} (last {_days(days)})")
    if (match := _RELATIVE.fullmatch(text)) and match[1] != "0":
        return _last(int(match[1] or 1) * UNIT_DAYS[match[2]])
    raise ToolError(
        f'Unknown date window {value!r}. Use a number of days, "last N days" (or weeks, '
        'months, years), "today", "this week", "this month" or "this year".'
    )


def _last(days: int) -> DateWindow:
    return DateWindow(days, f"last {_days(days)}")


def _days(days: int) -> str:
    return f"{days} day" if days == 1 else f"{days} days"


def _period_start(unit: str, now: float) -> datetime:
    today = datetime.fromtimestamp(now, UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    if unit == "week":
        return today - timedelta(days=today.weekday())
    if unit == "month":
        return today.replace(day=1)
    return today.replace(month=1, day=1)
