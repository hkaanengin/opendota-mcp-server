"""The OpenDota API key: sent as `?api_key=`, never leaked into logs or errors."""

import logging
from typing import Any

import httpx
import pytest
import respx

from tests.conftest import API_KEY, RECORDS, Connect


async def test_the_key_is_sent_as_the_api_key_query_parameter(
    connect: Connect, opendota: respx.MockRouter
) -> None:
    route = opendota.get("/records/kills").respond(json=RECORDS)

    async with connect(opendota_api_key=API_KEY) as client:
        await client.call_tool("get_records", {"field": "kills"})

    request = route.calls.last.request
    assert request.url.params["api_key"] == API_KEY
    assert "authorization" not in request.headers


async def test_without_a_key_no_api_key_parameter_is_sent(
    connect: Connect, opendota: respx.MockRouter
) -> None:
    route = opendota.get("/records/kills").respond(json=RECORDS)

    async with connect() as client:
        await client.call_tool("get_records", {"field": "kills"})

    assert "api_key" not in route.calls.last.request.url.params


async def test_the_key_never_appears_in_logs_or_error_messages(
    connect: Connect, opendota: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    responses: list[Any] = [
        httpx.Response(200, json=RECORDS),  # kills
        httpx.Response(429, headers={"Retry-After": "1"}),  # deaths
        httpx.Response(429, headers={"Retry-After": "1"}),
        httpx.Response(503),  # assists
        httpx.ReadTimeout("timed out"),  # last_hits
        httpx.Response(400, json={"error": f"Invalid API key {API_KEY}"}),  # denies
        httpx.Response(200, json={"not": "a list"}),  # duration
    ]
    opendota.get(path__startswith="/records/").mock(side_effect=responses)

    errors: list[str] = []
    async with connect(opendota_api_key=API_KEY) as client:
        for field in ("kills", "deaths", "assists", "last_hits", "denies", "duration"):
            result = await client.call_tool("get_records", {"field": field}, raise_on_error=False)
            errors.extend(getattr(block, "text", "") for block in result.content)

    assert opendota.calls.call_count == len(responses)
    assert "/records/kills" in caplog.text, "expected request logging to be captured"
    assert API_KEY not in caplog.text
    assert not [error for error in errors if API_KEY in error]
