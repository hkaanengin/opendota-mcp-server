"""In-memory OpenDota response cache, with a time limit per kind of data."""

from collections import OrderedDict
from collections.abc import Hashable
from typing import Any

from opendota_mcp.clock import Clock

PLAYER_TTL = 5 * 60.0
"""Player-scoped data: changes whenever the player finishes a game."""
HERO_WIDE_TTL = 6 * 60 * 60.0
"""Hero-wide data (matchups, benchmarks, meta, records, ...): drifts slowly."""
PARSED_MATCH_TTL: float | None = None
"""A finished, parsed match never changes, so it's kept until evicted."""
UNPARSED_MATCH_TTL = 2 * 60.0
"""An unparsed match may become parsed at any time."""

MAX_ENTRIES = 128
"""LRU cap. Parsed matches run to a few hundred KB each, so this bounds memory."""


class ResponseCache:
    """Entries expire after their own TTL (`None`: never) and the least recently used go first."""

    def __init__(self, clock: Clock, max_entries: int = MAX_ENTRIES) -> None:
        self._clock = clock
        self._max_entries = max_entries
        self._entries: OrderedDict[Hashable, tuple[float | None, Any]] = OrderedDict()

    def get(self, key: Hashable, default: Any = None) -> Any:
        entry = self._entries.get(key)
        if entry is None:
            return default
        expires_at, value = entry
        if expires_at is not None and self._clock.time() >= expires_at:
            del self._entries[key]
            return default
        self._entries.move_to_end(key)
        return value

    def put(self, key: Hashable, value: Any, ttl: float | None) -> None:
        expires_at = None if ttl is None else self._clock.time() + ttl
        self._entries[key] = (expires_at, value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
