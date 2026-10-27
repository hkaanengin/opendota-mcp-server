"""`get_player_breakdown`, `get_player_matches` and `get_player_rank_history`.

How each filter becomes a query parameter is covered once, in `test_player_win_loss`;
here each filtered tool is checked to pass the same filters on and disclose them.
"""

from typing import Any

import pytest
import respx
from fastmcp import Client

from tests.conftest import load_fixture
from tests.test_player_profile import AMMAR
from tests.test_player_stats import call, route
from tests.test_player_win_loss import PARSED_ONLY, STANDARD_GAMES, sent_query

MATCH_COLUMNS = [
    ("project", "assists"),
    ("project", "deaths"),
    ("project", "gold_per_min"),
    ("project", "hero_id"),
    ("project", "kills"),
    ("project", "start_time"),
    ("project", "xp_per_min"),
]
"""The columns `/matches` must be asked for: `project` replaces its default columns."""

RANKED_PLAYER = 10287287
"""A Player with a recorded rank history (Ammar has none)."""

FILTERED_TOOLS = {"get_player_breakdown": "counts", "get_player_matches": "matches"}
"""Tool → the `/players/{id}/...` endpoint it reads."""


def without_project(route: respx.Route) -> list[tuple[str, str]]:
    return [(key, value) for key, value in sent_query(route) if key != "project"]


async def test_breakdown_groups_wins_by_readable_labels(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route(opendota, "counts")

    data = await call(client, "get_player_breakdown")

    assert data["resolved_player"] == {"account_id": AMMAR, "persona_name": "Ammar"}
    assert data["game_modes"][:2] == [
        {"label": "All Pick", "games": 943, "wins": 519, "win_rate": 55.0},
        {"label": "Single Draft", "games": 298, "wins": 179, "win_rate": 60.1},
    ]
    assert data["lobby_types"][:2] == [
        {"label": "Ranked", "games": 827, "wins": 461, "win_rate": 55.7},
        {"label": "Unranked", "games": 468, "wins": 267, "win_rate": 57.1},
    ]
    assert [lane["label"] for lane in data["lanes"]] == [
        "safe lane",
        "mid lane",
        "off lane",
        "jungle",
        "unknown (match not parsed)",
    ]
    assert data["lanes"][0] == {"label": "safe lane", "games": 40, "wins": 24, "win_rate": 60.0}
    assert data["regions"] == [
        {"label": "Singapore", "games": 1299, "wins": 727, "win_rate": 56.0},
        {"label": "Europe", "games": 1, "wins": 1, "win_rate": 100.0},
    ]
    # Newest patch first, named by version rather than OpenDota's patch index.
    assert data["patches"][:3] == [
        {"label": "7.39", "games": 4, "wins": 3, "win_rate": 75.0},
        {"label": "7.37", "games": 2, "wins": 0, "win_rate": 0.0},
        {"label": "7.33", "games": 2, "wins": 1, "win_rate": 50.0},
    ]
    assert data["patches"][-1]["label"] == "6.83"


async def test_breakdown_names_ids_it_does_not_know(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get(f"/players/{AMMAR}").respond(json=load_fixture(f"players/{AMMAR}.json"))
    empty: dict[str, Any] = {"leaver_status": {}, "lobby_type": {}, "patch": {}}
    opendota.get(f"/players/{AMMAR}/counts").respond(
        json={
            **empty,
            "game_mode": {"99": {"games": 2, "win": 1}},
            "region": {"99": {"games": 2, "win": 1}},
            "lane_role": {"0": {"games": 3, "win": 1}, "9": {"games": 2, "win": 1}},
        }
    )

    data = await call(client, "get_player_breakdown")

    assert data["game_modes"][0]["label"] == "Game mode 99"
    assert data["regions"][0]["label"] == "Region 99"
    assert [lane["label"] for lane in data["lanes"]] == [
        "Unknown lane (id 9)",
        "unknown (match not parsed)",
    ]


async def test_matches_are_the_latest_20_by_default(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    sent = route(opendota, "matches")

    data = await call(client, "get_player_matches")

    assert sent_query(sent) == [("limit", "20"), *MATCH_COLUMNS]
    assert data["resolved_player"] == {"account_id": AMMAR, "persona_name": "Ammar"}
    assert len(data["matches"]) == 20
    assert data["matches"][0] == {
        "match_id": 8425246099,
        "hero": "Anti-Mage",
        "result": "loss",
        "kills": 1,
        "deaths": 7,
        "assists": 4,
        "gold_per_min": 335,
        "xp_per_min": 399,
        "duration": 1950,
        "duration_mmss": "32:30",
        "start_time": "2025-08-20T14:06:23Z",
        "game_mode": "All Pick",
        "lobby_type": "Unranked",
    }
    # Dire (slot 130) in a game Radiant lost.
    assert data["matches"][3]["result"] == "win"
    assert data["next_offset"] == 20


async def test_matches_page_with_limit_and_offset(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    sent = route(opendota, "matches")

    data = await call(client, "get_player_matches", filters={"limit": 50, "offset": 100})

    assert without_project(sent) == [("limit", "50"), ("offset", "100")]
    # Fewer rows than asked for: this was the last page.
    assert data["next_offset"] is None
    assert data["filters"]["applied"] == ["latest 50 matches", "skipping the latest 100"]


async def test_a_full_page_points_at_the_next(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route(opendota, "matches")

    data = await call(client, "get_player_matches", filters={"limit": 20, "offset": 40})

    assert data["next_offset"] == 60


async def test_rank_history_oldest_first_with_medal_names(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get(f"/players/{RANKED_PLAYER}").respond(
        json=load_fixture(f"players/{RANKED_PLAYER}.json")
    )
    ratings = load_fixture(f"players/{RANKED_PLAYER}_ratings.json")
    opendota.get(f"/players/{RANKED_PLAYER}/ratings").respond(json=list(reversed(ratings)))

    result = await client.call_tool("get_player_rank_history", {"player": RANKED_PLAYER})
    data = result.structured_content
    assert data is not None

    assert data["resolved_player"] == {"account_id": RANKED_PLAYER, "persona_name": "хукач"}
    assert data["current_rank"] == "Divine 3"
    assert data["changes"][:3] == [
        {"time": "2025-12-12T15:18:33.732000Z", "rank": "Divine 1"},
        {"time": "2026-01-28T16:45:17.303000Z", "rank": "Divine 2"},
        {"time": "2026-03-01T07:39:02.726000Z", "rank": "Divine 1"},
    ]
    assert data["changes"][-1]["rank"] == "Divine 3"
    assert len(data["changes"]) == 9


async def test_rank_history_can_be_empty(client: Client[Any], opendota: respx.MockRouter) -> None:
    opendota.get(f"/players/{AMMAR}").respond(json=load_fixture(f"players/{AMMAR}.json"))
    opendota.get(f"/players/{AMMAR}/ratings").respond(json=[])

    result = await client.call_tool("get_player_rank_history", {"player": AMMAR})

    assert result.structured_content is not None
    assert result.structured_content["changes"] == []


@pytest.mark.parametrize("tool", FILTERED_TOOLS)
async def test_each_tool_passes_filters_on_and_discloses_them(
    client: Client[Any], opendota: respx.MockRouter, tool: str
) -> None:
    sent = route(opendota, FILTERED_TOOLS[tool])

    data = await call(client, tool, filters={"hero": "pudge", "lane": "pos 1", "ranked_only": True})

    assert ("hero_id", "14") in sent_query(sent)
    assert ("lane_role", "1") in sent_query(sent)
    assert ("lobby_type", "7") in sent_query(sent)
    assert data["filters"]["applied"] == ["Ranked", "safe lane (pos 1)", "playing Pudge"]
    assert data["filters"]["parsed_only_note"] == PARSED_ONLY


@pytest.mark.parametrize("tool", FILTERED_TOOLS)
async def test_each_tool_leaves_turbo_out_by_default(
    client: Client[Any], opendota: respx.MockRouter, tool: str
) -> None:
    sent = route(opendota, FILTERED_TOOLS[tool])

    data = await call(client, tool)

    assert ("significant", "0") not in sent_query(sent)
    assert data["filters"]["game_modes"] == STANDARD_GAMES


@pytest.mark.parametrize(
    "tool", ["get_player_breakdown", "get_player_matches", "get_player_rank_history"]
)
async def test_each_tool_publishes_an_output_schema_and_is_read_only(
    client: Client[Any], tool: str
) -> None:
    tools = {listed.name: listed for listed in await client.list_tools()}

    listed = tools[tool]
    assert listed.annotations is not None
    assert listed.annotations.read_only_hint is True
    assert listed.output_schema is not None
    assert "resolved_player" in listed.output_schema["properties"]
    filtered = tool in FILTERED_TOOLS
    assert ("filters" in listed.output_schema["properties"]) is filtered
    assert ("filters" in listed.input_schema["properties"]) is filtered


async def test_the_old_recent_matches_tool_is_gone(client: Client[Any]) -> None:
    names = {listed.name for listed in await client.list_tools()}

    assert not any("recent" in name for name in names)
