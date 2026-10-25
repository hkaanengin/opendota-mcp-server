"""Shared output formatting, so every tool presents values the same way."""


def mmss(seconds: int | float) -> str:
    """Game time as `MM:SS`, minutes unbounded (e.g. 4325 → "72:05")."""
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def win_rate(wins: int, games: int) -> float | None:
    """Percent of games won, to one decimal (e.g. 728 of 1300 → 56.0); `None` with no games."""
    return round(100 * wins / games, 1) if games else None
