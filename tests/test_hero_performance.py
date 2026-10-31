"""`get_hero_lane_performance`, `get_hero_item_timings` and `get_hero_duration_performance`.

Recorded from OpenDota on 2026-10-31.
"""

from typing import Any

import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import FakeClock, api_calls, load_fixture

PUDGE_LANES = "heroes/scenarios_laneRoles_14.json"
BATTLE_FURY_TIMINGS = "heroes/scenarios_itemTimings_1_bfury.json"
ANTI_MAGE_DURATIONS = "heroes/1_durations.json"


async def call(client: Client[Any], tool: str, **arguments: Any) -> dict[str, Any]:
    result = await client.call_tool(tool, arguments)
    assert result.structured_content is not None
    return result.structured_content


def lane_roles(opendota: respx.MockRouter) -> respx.Route:
    return opendota.get("/scenarios/laneRoles", params={"hero_id": 14}).respond(
        json=load_fixture(PUDGE_LANES)
    )


def item_timings(opendota: respx.MockRouter) -> respx.Route:
    return opendota.get("/scenarios/itemTimings", params={"hero_id": 1, "item": "bfury"}).respond(
        json=load_fixture(BATTLE_FURY_TIMINGS)
    )


def durations(opendota: respx.MockRouter) -> respx.Route:
    return opendota.get("/heroes/1/durations").respond(json=load_fixture(ANTI_MAGE_DURATIONS))


async def test_lane_performance_defaults_to_every_lane(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    lane_roles(opendota)

    data = await call(client, "get_hero_lane_performance", hero="pudge")

    assert data["hero"] == "Pudge"
    assert data["lane_note"] is None
    assert "Parsed matches" in data["note"]
    assert "over 90:00 aren't counted" in data["note"]
    assert [(row["lane"], row["games"], row["win_rate"]) for row in data["lanes"]] == [
        ("safe lane", 706, 51.6),
        ("mid lane", 450, 49.6),
        ("off lane", 1365, 51.1),
        ("jungle", 3, 33.3),
    ]


async def test_lane_performance_breaks_a_lane_down_by_game_length(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    lane_roles(opendota)

    data = await call(client, "get_hero_lane_performance", hero="pudge", lane="safe lane")

    assert data["lane_note"] == "Filtered by safe lane."
    [safe] = data["lanes"]
    assert safe["by_game_length"][0] == {
        "up_to": 900,
        "up_to_mmss": "15:00",
        "games": 20,
        "win_rate": 65.0,
    }
    assert [row["up_to_mmss"] for row in safe["by_game_length"]] == [
        "15:00",
        "30:00",
        "45:00",
        "60:00",
        "90:00",
    ]


@pytest.mark.parametrize("lane", ["pos 4", "soft support", 4])
async def test_lane_performance_by_position_discloses_the_lane_it_maps_to(
    client: Client[Any], opendota: respx.MockRouter, lane: str | int
) -> None:
    lane_roles(opendota)

    data = await call(client, "get_hero_lane_performance", hero="pudge", lane=lane)

    assert [row["lane"] for row in data["lanes"]] == ["off lane"]
    assert data["lane_note"] == (
        "Filtered by off lane, where pos 4 plays. OpenDota doesn't record positions, so "
        "pos 3 and pos 4 can't be told apart."
    )


async def test_lane_performance_for_a_lane_without_games_says_zero_games(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/scenarios/laneRoles").respond(json=[])

    data = await call(client, "get_hero_lane_performance", hero="pudge", lane="jungle")

    assert data["lanes"] == [{"lane": "jungle", "games": 0, "win_rate": None, "by_game_length": []}]


async def test_every_lane_is_answered_from_one_cached_request(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route = lane_roles(opendota)

    await call(client, "get_hero_lane_performance", hero="pudge")
    await call(client, "get_hero_lane_performance", hero="pudge", lane="mid")
    await call(client, "get_hero_lane_performance", hero="pudge", lane="pos 1")

    assert route.call_count == 1


@pytest.mark.parametrize(("lane", "expected"), [("support", "pos 4"), ("top", "Unknown lane")])
async def test_unusable_lane_fails_without_calling_opendota(
    client: Client[Any], opendota: respx.MockRouter, lane: str, expected: str
) -> None:
    with pytest.raises(ToolError, match=expected):
        await call(client, "get_hero_lane_performance", hero="pudge", lane=lane)

    assert api_calls(opendota) == 0


@pytest.mark.parametrize("item", ["Battle Fury", "bfury", "bf", "battle fuyr"])
async def test_item_timings_accept_item_names_and_spellings(
    client: Client[Any], opendota: respx.MockRouter, item: str
) -> None:
    item_timings(opendota)

    data = await call(client, "get_hero_item_timings", hero="am", item=item)

    assert data["hero"] == "Anti-Mage"
    assert data["item"] == "Battle Fury"


async def test_item_timings_accept_nicknames(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route = opendota.get(
        "/scenarios/itemTimings", params={"hero_id": 1, "item": "black_king_bar"}
    ).respond(
        json=[{"hero_id": 1, "item": "black_king_bar", "time": 1500, "games": "3", "wins": "2"}]
    )

    data = await call(client, "get_hero_item_timings", hero="am", item="bkb")

    assert route.call_count == 1
    assert data["item"] == "Black King Bar"
    assert data["timings"] == [
        {"bought_by": 1500, "bought_by_mmss": "25:00", "games": 3, "win_rate": 66.7}
    ]


async def test_item_timings_come_back_earliest_first_with_numeric_win_rates(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    item_timings(opendota)

    data = await call(client, "get_hero_item_timings", hero="am", item="Battle Fury")

    assert "Parsed matches" in data["note"]
    assert "after 30:00 aren't counted" in data["note"]
    assert data["timings"][:3] == [
        {"bought_by": 450, "bought_by_mmss": "07:30", "games": 8, "win_rate": 75.0},
        {"bought_by": 600, "bought_by_mmss": "10:00", "games": 31, "win_rate": 54.8},
        {"bought_by": 720, "bought_by_mmss": "12:00", "games": 209, "win_rate": 70.3},
    ]
    assert [row["bought_by"] for row in data["timings"]] == [
        450,
        600,
        720,
        900,
        1200,
        1500,
        1800,
    ]


async def test_item_without_timings_fails_explaining_the_cost_threshold(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    # OpenDota answers an empty list for items under 1400 gold, e.g. Tango.
    opendota.get("/scenarios/itemTimings").respond(json=[])

    with pytest.raises(ToolError) as error:
        await call(client, "get_hero_item_timings", hero="pudge", item="tango")

    message = str(error.value)
    assert "Tango" in message
    assert "Pudge" in message
    assert "1400 gold" in message
    assert "get_hero_item_popularity" in message


async def test_unknown_item_fails_with_a_suggestion_without_calling_opendota(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    with pytest.raises(ToolError, match="Black King Bar"):
        await call(client, "get_hero_item_timings", hero="am", item="black king staff")

    assert api_calls(opendota) == 0


async def test_duration_performance_is_shortest_first_and_labelled_as_pro_data(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    durations(opendota)

    data = await call(client, "get_hero_duration_performance", hero="am")

    assert data["hero"] == "Anti-Mage"
    assert data["data_source"] == "Pro matches"
    assert "Pro matches" in data["note"]
    assert data["durations"][0] == {
        "start": 300,
        "start_mmss": "05:00",
        "end": 600,
        "end_mmss": "10:00",
        "games": 24,
        "win_rate": 41.7,
    }
    assert data["durations"][8] == {
        "start": 2700,
        "start_mmss": "45:00",
        "end": 3000,
        "end_mmss": "50:00",
        "games": 824,
        "win_rate": 58.1,
    }
    starts = [row["start"] for row in data["durations"]]
    assert starts == sorted(starts)
    assert len(starts) == 23


HERO_PERFORMANCE_TOOLS = {
    "get_hero_lane_performance": {"hero", "lanes", "lane_note", "note"},
    "get_hero_item_timings": {"hero", "item", "timings", "note"},
    "get_hero_duration_performance": {"hero", "data_source", "durations", "note"},
}


@pytest.mark.parametrize(("tool", "fields"), HERO_PERFORMANCE_TOOLS.items())
async def test_tools_publish_an_output_schema_and_are_read_only(
    client: Client[Any], tool: str, fields: set[str]
) -> None:
    tools = {listed.name: listed for listed in await client.list_tools()}

    listed = tools[tool]
    assert listed.annotations is not None
    assert listed.annotations.read_only_hint is True
    assert listed.output_schema is not None
    assert fields <= set(listed.output_schema["properties"])


TOOL_CALLS: dict[str, tuple[Any, dict[str, Any]]] = {
    "get_hero_lane_performance": (lane_roles, {"hero": "pudge"}),
    "get_hero_item_timings": (item_timings, {"hero": "am", "item": "Battle Fury"}),
    "get_hero_duration_performance": (durations, {"hero": "am"}),
}


@pytest.mark.parametrize(("tool", "setup"), TOOL_CALLS.items())
async def test_responses_are_cached_for_six_hours(
    client: Client[Any],
    opendota: respx.MockRouter,
    clock: FakeClock,
    tool: str,
    setup: tuple[Any, dict[str, Any]],
) -> None:
    route_for, arguments = setup
    route = route_for(opendota)

    await call(client, tool, **arguments)
    clock.advance(6 * 60 * 60 - 1)
    await call(client, tool, **arguments)
    assert route.call_count == 1

    clock.advance(1)
    await call(client, tool, **arguments)
    assert route.call_count == 2


@pytest.mark.parametrize(("tool", "setup"), TOOL_CALLS.items())
async def test_unknown_hero_fails_with_a_suggestion_without_calling_opendota(
    client: Client[Any], opendota: respx.MockRouter, tool: str, setup: tuple[Any, dict[str, Any]]
) -> None:
    _, arguments = setup

    with pytest.raises(ToolError, match="Rubick"):
        await call(client, tool, **{**arguments, "hero": "rubek"})

    assert api_calls(opendota) == 0
