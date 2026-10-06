"""OpenDota response shapes, as OpenDota sends them (IDs, epoch seconds)."""

from pydantic import BaseModel

RECORD_FIELDS = (
    "kills",
    "deaths",
    "assists",
    "gold_per_min",
    "xp_per_min",
    "last_hits",
    "denies",
    "hero_damage",
    "tower_damage",
    "hero_healing",
    "duration",
)
"""Stats `/records/{field}` has data for. Any other field silently returns `[]`."""


class RecordEntry(BaseModel):
    match_id: int
    start_time: int
    hero_id: int
    score: int | float
