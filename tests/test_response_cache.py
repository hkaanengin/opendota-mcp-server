"""Response caching, observed by counting outbound OpenDota requests."""

from typing import Any

import respx
from fastmcp import Client

from tests.conftest import RECORDS, Connect, FakeClock

SIX_HOURS = 6 * 60 * 60


async def test_hero_wide_data_is_answered_from_cache_for_six_hours(
    client: Client[Any], opendota: respx.MockRouter, clock: FakeClock
) -> None:
    route = opendota.get("/records/kills").respond(json=RECORDS)

    await client.call_tool("get_records", {"field": "kills"})
    clock.advance(SIX_HOURS - 1)
    await client.call_tool("get_records", {"field": "Kills"})
    assert route.call_count == 1

    clock.advance(1)
    await client.call_tool("get_records", {"field": "kills"})
    assert route.call_count == 2


async def test_cached_answers_match_the_original(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/records/kills").respond(json=RECORDS)

    first = await client.call_tool("get_records", {"field": "kills"})
    second = await client.call_tool("get_records", {"field": "kills"})

    assert second.structured_content == first.structured_content


async def test_each_request_is_cached_separately(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    kills = opendota.get("/records/kills").respond(json=RECORDS)
    deaths = opendota.get("/records/deaths").respond(json=RECORDS)

    for field in ("kills", "deaths", "kills", "deaths"):
        await client.call_tool("get_records", {"field": field})

    assert (kills.call_count, deaths.call_count) == (1, 1)


async def test_cache_hits_never_consume_rate_limit_budget(
    connect: Connect, opendota: respx.MockRouter, clock: FakeClock
) -> None:
    opendota.get("/records/kills").respond(json=RECORDS)
    opendota.get("/records/deaths").respond(json=RECORDS)

    async with connect(opendota_rate_limit_rpm=1) as client:
        for _ in range(5):
            await client.call_tool("get_records", {"field": "kills"})
        assert clock.sleeps == []

        await client.call_tool("get_records", {"field": "deaths"})

    assert len(clock.sleeps) == 1


async def test_failures_are_not_cached(client: Client[Any], opendota: respx.MockRouter) -> None:
    route = opendota.get("/records/kills")
    route.side_effect = [respx.MockResponse(500), respx.MockResponse(200, json=RECORDS)]

    first = await client.call_tool("get_records", {"field": "kills"}, raise_on_error=False)
    second = await client.call_tool("get_records", {"field": "kills"})

    assert first.is_error
    assert second.structured_content is not None
    assert route.call_count == 2
