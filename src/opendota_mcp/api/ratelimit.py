"""Paces outbound OpenDota calls to stay inside its per-minute limit."""

import asyncio
import logging

from opendota_mcp.clock import Clock

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60.0


def seconds_until_next_window(now: float) -> float:
    """OpenDota's window is a fixed block that resets at the start of each wall-clock minute."""
    return WINDOW_SECONDS - now % WINDOW_SECONDS


class RateLimiter:
    """A fixed one-minute window with per-call costs, matching OpenDota's own counting."""

    def __init__(self, limit_per_minute: int, clock: Clock) -> None:
        self._limit = limit_per_minute
        self._clock = clock
        self._window: float | None = None
        self._used = 0
        self._lock = asyncio.Lock()

    async def acquire(self, cost: int = 1) -> None:
        """Spend `cost` calls from this minute's budget, waiting for the next minute if short.

        A call costing more than the whole budget still goes out, alone in a fresh window.
        """
        async with self._lock:
            self._roll_window()
            if self._used and self._used + cost > self._limit:
                wait = seconds_until_next_window(self._clock.time())
                logger.info(
                    "OpenDota rate limit of %d/min reached; waiting %.1fs", self._limit, wait
                )
                await self._clock.sleep(wait)
                self._roll_window()
            self._used += cost

    def _roll_window(self) -> None:
        window = self._clock.time() // WINDOW_SECONDS
        if window != self._window:
            self._window = window
            self._used = 0
