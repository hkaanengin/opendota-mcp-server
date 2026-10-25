"""Wall time behind a seam, so tests can control waits instead of sleeping."""

import asyncio
import time
from typing import Protocol


class Clock(Protocol):
    def time(self) -> float: ...

    async def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def time(self) -> float:
        # Wall time, not monotonic: OpenDota's rate-limit window resets on the minute.
        # The response cache shares this clock, so a system clock jump also shifts expiry;
        # acceptable for TTLs measured in minutes and hours.
        return time.time()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
