from datetime import date
from typing import Any

import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import load_fixture


def one_record(**overrides: Any) -> list[dict[str, Any]]:
    """A `/records/{field}` response with a single entry, shaped like the recorded one."""
    entry = {"match_id": 9029559560, "start_time": 1791134272, "hero_id": 72, "score": 2117}
    return [{**entry, **overrides}]


async def test_highest_gpm_ever_returns_ranked_records_with_hero_names(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/records/gold_per_min").respond(json=load_fixture("records_gold_per_min.json"))

    result = await client.call_tool("get_records", {"field": "gold_per_min"})

    data = result.structured_content
    assert data is not None
    assert data["stat"] == "gold_per_min"
    assert len(data["records"]) == 100
    assert data["records"][0] == {
        "rank": 1,
        "value": 2117,
        "value_mmss": None,
        "hero": "Gyrocopter",
        "match_id": 9029559560,
        "played_on": date(2026, 10, 4).isoformat(),
    }
    assert [r["rank"] for r in data["records"][:3]] == [1, 2, 3]


@pytest.mark.parametrize(
    ("asked", "stat"),
    [
        ("gpm", "gold_per_min"),
        ("GPM", "gold_per_min"),
        ("Last Hits", "last_hits"),
        ("cs", "last_hits"),
        ("hero-damage", "hero_damage"),
        ("tower damage", "tower_damage"),
        ("gold per minut", "gold_per_min"),
        ("assits", "assists"),
        ("game length", "duration"),
    ],
)
async def test_everyday_stat_words_resolve_to_the_opendota_field(
    client: Client[Any], opendota: respx.MockRouter, asked: str, stat: str
) -> None:
    route = opendota.get(f"/records/{stat}").respond(json=one_record())

    result = await client.call_tool("get_records", {"field": asked})

    assert route.call_count == 1
    assert result.structured_content is not None
    assert result.structured_content["stat"] == stat


@pytest.mark.parametrize("asked", ["kda", "actions per min", "net worth", ""])
async def test_unknown_stat_fails_listing_valid_stats_without_calling_opendota(
    client: Client[Any], opendota: respx.MockRouter, asked: str
) -> None:
    with pytest.raises(ToolError) as error:
        await client.call_tool("get_records", {"field": asked})

    message = str(error.value)
    assert f"Unknown stat {asked!r}" in message
    for valid in ("kills", "gold_per_min", "last_hits", "tower_damage", "duration"):
        assert valid in message
    assert opendota.calls.call_count == 0


async def test_duration_records_also_read_as_mmss(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/records/duration").respond(json=one_record(score=16954))

    result = await client.call_tool("get_records", {"field": "duration"})

    assert result.structured_content is not None
    record = result.structured_content["records"][0]
    assert record["value"] == 16954
    assert record["value_mmss"] == "282:34"


async def test_a_hero_missing_from_reference_data_still_reads_as_a_name(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/records/kills").respond(json=one_record(hero_id=999))

    result = await client.call_tool("get_records", {"field": "kills"})

    assert result.structured_content is not None
    assert result.structured_content["records"][0]["hero"] == "Unknown hero (id 999)"


async def test_get_records_publishes_an_output_schema_and_is_read_only(
    client: Client[Any],
) -> None:
    tools = {tool.name: tool for tool in await client.list_tools()}

    tool = tools["get_records"]
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.output_schema is not None
    assert {"stat", "records"} <= set(tool.output_schema["properties"])


@pytest.mark.parametrize(
    "response",
    [
        {"json": {"not": "a list"}},
        {"status_code": 500, "text": "Internal Server Error"},
    ],
    ids=["malformed payload", "server error"],
)
async def test_unexpected_failure_is_an_mcp_error_without_internals(
    client: Client[Any], opendota: respx.MockRouter, response: dict[str, Any]
) -> None:
    opendota.get("/records/kills").respond(**response)

    result = await client.call_tool("get_records", {"field": "kills"}, raise_on_error=False)

    assert result.is_error is True
    assert result.structured_content is None
    text = " ".join(getattr(block, "text", "") for block in result.content)
    assert "get_records" in text
    assert "validation" not in text.lower()
    assert "api.opendota.com" not in text
