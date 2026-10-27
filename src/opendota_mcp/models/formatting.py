"""Shared output formatting, so every tool presents values the same way."""

from datetime import UTC, date, datetime

STAT_NAMES: dict[str, str] = {
    "kills": "Kills",
    "deaths": "Deaths",
    "assists": "Assists",
    "kda": "KDA ratio",
    "gold_per_min": "Gold per minute",
    "xp_per_min": "Experience per minute",
    "last_hits": "Last hits",
    "denies": "Denies",
    "lane_efficiency_pct": "Lane efficiency (%)",
    "duration": "Match duration (seconds)",
    "level": "Hero level",
    "hero_damage": "Hero damage",
    "tower_damage": "Tower damage",
    "hero_healing": "Hero healing",
    "stuns": "Stun duration dealt (seconds)",
    "tower_kills": "Towers destroyed",
    "neutral_kills": "Neutral creeps killed",
    "courier_kills": "Couriers killed",
    "purchase_tpscroll": "Town Portal Scrolls bought",
    "purchase_ward_observer": "Observer wards bought",
    "purchase_ward_sentry": "Sentry wards bought",
    "purchase_gem": "Gems of True Sight bought",
    "purchase_rapier": "Divine Rapiers bought",
    "pings": "Map pings",
    "throw": "Biggest gold lead thrown (lost games)",
    "comeback": "Biggest gold deficit overcome (won games)",
    "stomp": "Biggest gold lead (won games)",
    "loss": "Biggest gold deficit (lost games)",
    "actions_per_min": "Actions per minute",
}
"""OpenDota stat field → how to show it."""


def stat_name(field: str) -> str:
    """A readable name for an OpenDota stat field, even one added after this table."""
    return STAT_NAMES.get(field) or field.replace("_", " ").capitalize()


def mmss(seconds: int | float) -> str:
    """Game time as `MM:SS`, minutes unbounded (e.g. 4325 → "72:05")."""
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def win_rate(wins: int, games: int) -> float | None:
    """Percent of games won, to one decimal (e.g. 728 of 1300 → 56.0); `None` with no games."""
    return round(100 * wins / games, 1) if games else None


def utc_date(epoch: int) -> date:
    """The UTC calendar date of an OpenDota epoch-seconds timestamp."""
    return datetime.fromtimestamp(epoch, tz=UTC).date()


def utc_datetime(epoch: int) -> datetime:
    """An OpenDota epoch-seconds timestamp as a UTC datetime."""
    return datetime.fromtimestamp(epoch, tz=UTC)
