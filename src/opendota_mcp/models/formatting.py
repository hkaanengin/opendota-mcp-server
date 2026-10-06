"""Shared output formatting, so every tool presents values the same way."""


def mmss(seconds: int | float) -> str:
    """Game time as `MM:SS`, minutes unbounded (e.g. 4325 → "72:05")."""
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"
