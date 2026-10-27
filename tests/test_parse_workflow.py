"""Parse requests and parse status, against recorded `/request` responses."""

from datetime import UTC, datetime
from typing import Any

import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import API_KEY, Connect, FakeClock, api_calls, load_fixture

MATCH_ID = 9032502907
JOB_ID = 418202651
JOB_TIME = datetime(2026, 10, 27, 18, 1, tzinfo=UTC).timestamp()
"""A minute after the recorded jobs were queued; the parsing one is locked until 18:04."""


def parsed_copy() -> dict[str, Any]:
    """The unparsed match as it reads once OpenDota has parsed it."""
    match = load_fixture(f"matches/{MATCH_ID}_unparsed.json")
    return {**match, "od_data": {**match["od_data"], "has_parsed": True}, "version": 22}


@pytest.fixture
def requested(opendota: respx.MockRouter) -> respx.Route:
    return opendota.post(f"/request/{MATCH_ID}").respond(
        json=load_fixture(f"request/{MATCH_ID}_requested.json")
    )


@pytest.fixture
def match(opendota: respx.MockRouter) -> respx.Route:
    """Unparsed at first; `match.side_effect = ...` changes what later fetches see."""
    return opendota.get(f"/matches/{MATCH_ID}").respond(
        json=load_fixture(f"matches/{MATCH_ID}_unparsed.json")
    )


def job(opendota: respx.MockRouter, state: str | None) -> respx.Route:
    route = opendota.get(f"/request/{JOB_ID}")
    if state is None:
        # A finished or unknown job: OpenDota sends a literal `null`.
        return route.respond(content=b"null", content_type="application/json")
    return route.respond(json=load_fixture(f"request/{JOB_ID}_{state}.json"))


async def request_parse(client: Client[Any]) -> dict[str, Any]:
    result = await client.call_tool("request_match_parse", {"match_id": MATCH_ID})
    assert result.structured_content is not None
    return result.structured_content


async def parse_status(client: Client[Any], **args: Any) -> dict[str, Any]:
    result = await client.call_tool("get_match_parse_status", {"match_id": MATCH_ID, **args})
    assert result.structured_content is not None
    return result.structured_content


async def test_request_returns_the_job_at_once_without_waiting(
    client: Client[Any], opendota: respx.MockRouter, requested: respx.Route
) -> None:
    result = await request_parse(client)

    assert result["match_id"] == MATCH_ID
    assert result["job_id"] == JOB_ID
    assert "few minutes" in result["message"]
    assert "get_match_parse_status" in result["message"]
    assert requested.call_count == 1
    assert api_calls(opendota) == 1  # no polling of the job or the match


async def test_request_for_an_unknown_match_explains(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.post(f"/request/{MATCH_ID}").respond(400, json={"error": "match ID not found"})

    with pytest.raises(ToolError, match=f"{MATCH_ID}"):
        await client.call_tool("request_match_parse", {"match_id": MATCH_ID})


async def test_request_costs_ten_against_the_rate_limit(
    connect: Connect, opendota: respx.MockRouter, clock: FakeClock, requested: respx.Route
) -> None:
    opendota.get("/records/kills").respond(500)

    async with connect(opendota_rate_limit_rpm=12) as client:
        clock.now = JOB_TIME + 15
        clock.sleeps.clear()
        await request_parse(client)
        for _ in range(2):
            await client.call_tool("get_records", {"field": "kills"}, raise_on_error=False)
        assert clock.sleeps == []

        await client.call_tool("get_records", {"field": "kills"}, raise_on_error=False)

    assert clock.sleeps == [45]


async def test_request_sends_the_api_key_as_a_query_param_for_parse_priority(
    connect: Connect, requested: respx.Route
) -> None:
    async with connect(opendota_api_key=API_KEY) as client:
        await request_parse(client)

    assert requested.calls.last.request.url.params["api_key"] == API_KEY


@pytest.mark.parametrize("state", ["queued", "parsing"])
async def test_status_reports_a_job_still_in_the_queue(
    client: Client[Any],
    opendota: respx.MockRouter,
    clock: FakeClock,
    requested: respx.Route,
    match: respx.Route,
    state: str,
) -> None:
    job(opendota, state)
    await request_parse(client)
    clock.now = JOB_TIME

    status = await parse_status(client)

    assert status["status"] == state
    assert status["job_id"] == JOB_ID
    assert match.call_count == 0  # the job alone answers it


async def test_status_reports_parsed_once_the_job_is_done(
    client: Client[Any], opendota: respx.MockRouter, requested: respx.Route, match: respx.Route
) -> None:
    job(opendota, None)
    match.respond(json=parsed_copy())
    await request_parse(client)

    status = await parse_status(client)

    assert status["status"] == "parsed"
    assert "get_match_section" in status["message"]


async def test_status_reports_failed_when_the_job_ended_but_the_match_is_unparsed(
    client: Client[Any], opendota: respx.MockRouter, requested: respx.Route, match: respx.Route
) -> None:
    job(opendota, None)
    await request_parse(client)

    status = await parse_status(client)

    assert status["status"] == "failed"
    assert "replay" in status["message"]


async def test_status_accepts_the_job_id_from_an_earlier_session(
    client: Client[Any], opendota: respx.MockRouter, clock: FakeClock, match: respx.Route
) -> None:
    route = job(opendota, "queued")
    clock.now = JOB_TIME

    status = await parse_status(client, job_id=JOB_ID)

    assert status["status"] == "queued"
    assert route.call_count == 1


async def test_status_without_a_known_job_checks_the_match_only(
    client: Client[Any], opendota: respx.MockRouter, match: respx.Route
) -> None:
    status = await parse_status(client)

    assert status["status"] == "not_requested"
    assert status["job_id"] is None
    assert "request_match_parse" in status["message"]
    assert api_calls(opendota) == 1


async def test_status_of_an_already_parsed_match_is_parsed(
    client: Client[Any], match: respx.Route
) -> None:
    match.respond(json=parsed_copy())

    assert (await parse_status(client))["status"] == "parsed"


async def test_a_match_found_parsed_replaces_the_cached_unparsed_copy(
    client: Client[Any], opendota: respx.MockRouter, requested: respx.Route, match: respx.Route
) -> None:
    job(opendota, None)
    before = await client.call_tool("get_match", {"match_id": MATCH_ID})
    assert before.structured_content is not None
    assert before.structured_content["parsed"] is False

    await request_parse(client)
    match.respond(json=parsed_copy())
    assert (await parse_status(client))["status"] == "parsed"
    after = await client.call_tool("get_match", {"match_id": MATCH_ID})

    assert after.structured_content is not None
    assert after.structured_content["parsed"] is True
    assert match.call_count == 2  # the status check's fetch is the copy get_match now serves


async def test_parse_tools_publish_output_schemas_and_only_the_request_writes(
    client: Client[Any],
) -> None:
    tools = {tool.name: tool for tool in await client.list_tools()}

    request, status = tools["request_match_parse"], tools["get_match_parse_status"]
    assert request.annotations is not None
    assert request.annotations.read_only_hint is False
    assert status.annotations is not None
    assert status.annotations.read_only_hint is True
    assert {"job_id", "message"} <= set(request.output_schema["properties"])  # type: ignore[index]
    assert {"status", "message"} <= set(status.output_schema["properties"])  # type: ignore[index]
    others = [tool for name, tool in tools.items() if name != "request_match_parse"]
    assert all(tool.annotations and tool.annotations.read_only_hint for tool in others)
