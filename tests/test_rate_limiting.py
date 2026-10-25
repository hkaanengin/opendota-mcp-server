"""Rate limiting and OpenDota failures, observed through tool calls and the fake clock.

`get_records` responses are cached, so tests that need many uncached calls answer with
a 500: failed calls are never cached but still count against OpenDota's limit.
"""

from typing import Any

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import API_KEY, RECORDS, Connect, FakeClock, api_calls

MINUTE_START = 60 * 20_000.0
"""A fake-clock time exactly on a minute boundary, where OpenDota's window resets."""


def start_window(clock: FakeClock, at: float) -> None:
    """Move to `at`, a fresh minute after the startup `/constants/*` fetches, and forget
    any waits those fetches caused, so a test sees only its own calls' budget."""
    clock.now = at
    clock.sleeps.clear()


async def call_failing(client: Client[Any], times: int) -> None:
    for _ in range(times):
        result = await client.call_tool("get_records", {"field": "kills"}, raise_on_error=False)
        assert result.is_error


@pytest.mark.parametrize(
    ("settings", "limit"),
    [
        ({}, 55),
        ({"opendota_api_key": API_KEY}, 290),
        ({"opendota_rate_limit_rpm": 3}, 3),
        ({"opendota_api_key": API_KEY, "opendota_rate_limit_rpm": 3}, 3),
    ],
    ids=["anonymous", "with key", "override", "override with key"],
)
async def test_calls_beyond_the_minute_limit_wait_for_the_next_minute(
    connect: Connect,
    opendota: respx.MockRouter,
    clock: FakeClock,
    settings: dict[str, Any],
    limit: int,
) -> None:
    opendota.get("/records/kills").respond(500)

    async with connect(**settings) as client:
        start_window(clock, MINUTE_START + 15)
        await call_failing(client, limit)
        assert clock.sleeps == []

        await call_failing(client, 1)

    assert clock.sleeps == [45]
    assert api_calls(opendota) == limit + 1


async def test_the_window_is_a_fixed_minute_not_a_sliding_one(
    connect: Connect, opendota: respx.MockRouter, clock: FakeClock
) -> None:
    opendota.get("/records/kills").respond(500)

    async with connect(opendota_rate_limit_rpm=2) as client:
        start_window(clock, MINUTE_START + 50)
        await call_failing(client, 2)
        clock.advance(10)  # a new minute: the budget is back, though the calls were 10s ago
        await call_failing(client, 2)
        assert clock.sleeps == []

        await call_failing(client, 1)

    assert clock.sleeps == [60]


async def test_a_burst_spanning_several_minutes_keeps_waiting(
    connect: Connect, opendota: respx.MockRouter, clock: FakeClock
) -> None:
    opendota.get("/records/kills").respond(500)

    async with connect(opendota_rate_limit_rpm=2) as client:
        start_window(clock, MINUTE_START)
        await call_failing(client, 5)

    assert clock.sleeps == [60, 60]


async def test_a_429_is_retried_once_after_retry_after(
    client: Client[Any], opendota: respx.MockRouter, clock: FakeClock
) -> None:
    opendota.get("/records/kills").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}, json={"error": "rate limited"}),
            httpx.Response(200, json=RECORDS),
        ]
    )

    result = await client.call_tool("get_records", {"field": "kills"})

    assert result.structured_content is not None
    assert len(result.structured_content["records"]) == 1
    assert clock.sleeps == [7]
    assert api_calls(opendota) == 2


async def test_a_second_429_fails_saying_the_limit_was_hit_and_when_to_retry(
    client: Client[Any], opendota: respx.MockRouter, clock: FakeClock
) -> None:
    opendota.get("/records/kills").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(429, headers={"Retry-After": "40"}),
        ]
    )

    with pytest.raises(ToolError) as error:
        await client.call_tool("get_records", {"field": "kills"})

    assert str(error.value) == "OpenDota rate limit hit, try again in 40s."
    assert clock.sleeps == [7]
    assert api_calls(opendota) == 2


async def test_a_429_without_retry_after_waits_for_the_next_minute(
    client: Client[Any], opendota: respx.MockRouter, clock: FakeClock
) -> None:
    clock.now = MINUTE_START + 48
    opendota.get("/records/kills").mock(
        side_effect=[httpx.Response(429), httpx.Response(200, json=RECORDS)]
    )

    await client.call_tool("get_records", {"field": "kills"})

    assert clock.sleeps == [12]


async def test_a_429_with_a_long_retry_after_fails_at_once_instead_of_hanging(
    client: Client[Any], opendota: respx.MockRouter, clock: FakeClock
) -> None:
    opendota.get("/records/kills").respond(
        429, headers={"Retry-After": "5400"}, json={"error": "daily api limit exceeded"}
    )

    with pytest.raises(ToolError) as error:
        await client.call_tool("get_records", {"field": "kills"})

    assert str(error.value) == "OpenDota rate limit hit, try again in 90 min."
    assert clock.sleeps == []
    assert api_calls(opendota) == 1


@pytest.mark.parametrize("status", [500, 502, 503, 504])
async def test_an_opendota_server_error_says_to_try_again_later(
    client: Client[Any], opendota: respx.MockRouter, status: int
) -> None:
    opendota.get("/records/kills").respond(status)

    with pytest.raises(ToolError) as error:
        await client.call_tool("get_records", {"field": "kills"})

    assert str(error.value) == (
        f"OpenDota is having problems (HTTP {status}). Try again in a few minutes."
    )


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ReadTimeout("timed out"),
        httpx.ConnectTimeout("timed out"),
        httpx.ConnectError("connection refused"),
    ],
    ids=["read timeout", "connect timeout", "connection refused"],
)
async def test_an_unreachable_opendota_says_to_try_again_later(
    client: Client[Any], opendota: respx.MockRouter, failure: Exception
) -> None:
    opendota.get("/records/kills").mock(side_effect=failure)

    with pytest.raises(ToolError) as error:
        await client.call_tool("get_records", {"field": "kills"})

    assert str(error.value) == "OpenDota didn't respond. Try again in a few minutes."
