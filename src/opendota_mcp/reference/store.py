"""Keeps the reference data current: live from OpenDota, refreshed daily, bundled as fallback."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from opendota_mcp.api import OpenDotaClient
from opendota_mcp.clock import Clock
from opendota_mcp.reference.data import Reference

logger = logging.getLogger(__name__)

REFRESH_INTERVAL = 24 * 60 * 60.0
"""Hero and item data changes with patches, a few times a year."""
RETRY_INTERVAL = 15 * 60.0
"""After a failed fetch, try again sooner than a day, but not on every tool call."""


class ReferenceStore:
    """Starts on the bundled snapshots and swaps in live data per resource as it arrives.

    A resource that fails to fetch or validate keeps the data it had, so a bad answer
    from OpenDota never takes hero or item lookups down.
    """

    def __init__(self, api: OpenDotaClient, clock: Clock) -> None:
        self._clock = clock
        self._reference = Reference.bundled()
        self._refresh_at = 0.0
        self._lock = asyncio.Lock()
        self._fetchers: dict[str, Callable[[], Awaitable[Any]]] = {
            "heroes": api.get_hero_constants,
            "items": api.get_item_constants,
            "aghs_desc": api.get_aghs_desc_constants,
            "hero_lore": api.get_hero_lore_constants,
            "patch": api.get_patch_constants,
        }

    async def current(self) -> Reference:
        """The latest data, refreshing first when it's due."""
        if self._clock.time() >= self._refresh_at:
            async with self._lock:
                if self._clock.time() >= self._refresh_at:
                    await self._refresh()
        return self._reference

    async def _refresh(self) -> None:
        results = await asyncio.gather(
            *(fetch() for fetch in self._fetchers.values()), return_exceptions=True
        )
        fetched: dict[str, Any] = {}
        for resource, result in zip(self._fetchers, results, strict=True):
            if isinstance(result, Exception):
                logger.warning(
                    "Couldn't refresh /constants/%s (%s); keeping the data already loaded",
                    resource,
                    result,
                )
            elif isinstance(result, BaseException):
                raise result
            else:
                fetched[resource] = result
        self._reference = self._reference.with_parts(**fetched)
        complete = len(fetched) == len(self._fetchers)
        self._refresh_at = self._clock.time() + (REFRESH_INTERVAL if complete else RETRY_INTERVAL)
        logger.info("Loaded %d of %d reference resources from OpenDota", len(fetched), len(results))
