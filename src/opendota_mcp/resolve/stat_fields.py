"""Everyday stat words ("gpm", "last hits") → OpenDota field names."""

import difflib
import re
from collections.abc import Collection

from fastmcp.exceptions import ToolError

FUZZY_CUTOFF = 0.8

STAT_SYNONYMS: dict[str, str] = {
    "kill": "kills",
    "death": "deaths",
    "assist": "assists",
    "gpm": "gold_per_min",
    "gold per minute": "gold_per_min",
    "xpm": "xp_per_min",
    "xp per minute": "xp_per_min",
    "exp per min": "xp_per_min",
    "experience per minute": "xp_per_min",
    "lh": "last_hits",
    "cs": "last_hits",
    "creep score": "last_hits",
    "last hit": "last_hits",
    "deny": "denies",
    "denys": "denies",
    "damage": "hero_damage",
    "hd": "hero_damage",
    "hero dmg": "hero_damage",
    "td": "tower_damage",
    "building damage": "tower_damage",
    "tower dmg": "tower_damage",
    "healing": "hero_healing",
    "heal": "hero_healing",
    "hh": "hero_healing",
    "length": "duration",
    "game length": "duration",
    "match length": "duration",
    "match duration": "duration",
    "game duration": "duration",
    "kill death assist": "kda",
    "kda ratio": "kda",
    "apm": "actions_per_min",
    "actions per minute": "actions_per_min",
    "lane efficiency": "lane_efficiency_pct",
    "le": "lane_efficiency_pct",
    "hero level": "level",
    "stun": "stuns",
    "stun duration": "stuns",
    "towers": "tower_kills",
    "tower kill": "tower_kills",
    "neutrals": "neutral_kills",
    "neutral kill": "neutral_kills",
    "jungle creeps": "neutral_kills",
    "courier kill": "courier_kills",
    "couriers": "courier_kills",
    "tp": "purchase_tpscroll",
    "tps": "purchase_tpscroll",
    "tp scrolls": "purchase_tpscroll",
    "teleport scrolls": "purchase_tpscroll",
    "obs": "purchase_ward_observer",
    "observers": "purchase_ward_observer",
    "observer wards": "purchase_ward_observer",
    "sentries": "purchase_ward_sentry",
    "sentry wards": "purchase_ward_sentry",
    "gem": "purchase_gem",
    "gems": "purchase_gem",
    "rapier": "purchase_rapier",
    "rapiers": "purchase_rapier",
    "ping": "pings",
}
"""Everyday stat word (normalized, space-separated) → canonical field."""


def resolve_stat_field(text: str, valid: Collection[str]) -> str:
    """Resolve a stat to one of `valid`, by exact name, everyday synonym, then fuzzy spelling.

    Raises a `ToolError` listing the valid stats when nothing matches.
    """
    wanted = _normalize(text)
    names = {_normalize(field): field for field in valid}
    synonyms = {word: field for word, field in STAT_SYNONYMS.items() if field in valid}

    if wanted in names:
        return names[wanted]
    if wanted in synonyms:
        return synonyms[wanted]
    candidates = {**synonyms, **names}
    close = difflib.get_close_matches(wanted, candidates, n=1, cutoff=FUZZY_CUTOFF)
    if close:
        return candidates[close[0]]
    raise ToolError(f"Unknown stat {text!r}. Use one of: {', '.join(valid)}.")


def _normalize(text: str) -> str:
    return re.sub(r"[\s_\-]+", " ", text).strip().lower()
