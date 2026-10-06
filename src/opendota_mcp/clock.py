"""Wall time behind a seam, so tests can control waits instead of sleeping."""

import asyncio
import time
from typing import Protocol


class Clock(Protocol):
    def time(self) -> float: ...

    async def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def time(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
