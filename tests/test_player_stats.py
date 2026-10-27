"""`get_player_heroes`, `get_player_peers`, `get_player_totals` and `get_player_histogram`.

How each filter becomes a query parameter is covered once, in `test_player_win_loss`;
here each tool is checked to pass the same filters on and disclose them.
"""

from typing import Any

import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import api_calls, load_fixture
from tests.test_player_profile import AMMAR
from tests.test_player_win_loss import PARSED_ONLY, STANDARD_GAMES, sent_query

FILTERED_TOOLS = {
    "get_player_heroes": ("heroes", {}),
    "get_player_peers": ("peers", {}),
    "get_player_totals": ("totals", {}),
    "get_player_histogram": ("histograms/gold_per_min", {"field": "gpm"}),
}
"""Tool → the `/players/{id}/...` endpoint it reads, and its extra arguments."""


def route(opendota: respx.MockRouter, endpoint: str, fixture: str | None = None) -> respx.Route:
    """Ammar's profile (behind the resolved player) plus one recorded player endpoint."""
    opendota.get(f"/players/{AMMAR}").respond(json=load_fixture(f"players/{AMMAR}.json"))
    fixture = fixture or endpoint.replace("histograms/", "histogram_")
    return opendota.get(f"/players/{AMMAR}/{endpoint}").respond(
        json=load_fixture(f"players/{AMMAR}_{fixture}.json")
    )


async def call(client: Client[Any], tool: str, **arguments: Any) -> dict[str, Any]:
    result = await client.call_tool(tool, {"player": AMMAR, **arguments})
    assert result.structured_content is not None
    return result.structured_content


async def test_heroes_by_name_with_win_rates_most_played_first(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route(opendota, "heroes")

    data = await call(client, "get_player_heroes")

    assert data["resolved_player"] == {"account_id": AMMAR, "persona_name": "Ammar"}
    assert data["heroes"][:3] == [
        {"hero": "Nature's Prophet", "games": 121, "wins": 66, "win_rate": 54.5},
        {"hero": "Juggernaut", "games": 91, "wins": 57, "win_rate": 62.6},
        {"hero": "Invoker", "games": 83, "wins": 53, "win_rate": 63.9},
    ]
    # Heroes never played are left out by default.
    assert len(data["heroes"]) == 127 - 16
    assert all(hero["games"] >= 1 for hero in data["heroes"])


async def test_heroes_below_min_games_are_left_out(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    heroes = route(opendota, "heroes")

    data = await call(client, "get_player_heroes", min_games=36)

    assert [hero["hero"] for hero in data["heroes"]] == [
        "Nature's Prophet",
        "Juggernaut",
        "Invoker",
        "Drow Ranger",
        "Nyx Assassin",
        "Anti-Mage",
    ]
    # Applied here rather than sent to OpenDota, so every threshold shares one cached response.
    assert sent_query(heroes) == []


async def test_peers_with_games_and_win_rate_together(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route(opendota, "peers")

    data = await call(client, "get_player_peers")

    assert data["peers"][:2] == [
        {
            "persona_name": "Rizoct",
            "account_id": 287105560,
            "games": 354,
            "wins": 199,
            "win_rate": 56.2,
            "last_played_date": "2019-07-28",
        },
        {
            "persona_name": "Oira",
            "account_id": 229458761,
            "games": 317,
            "wins": 179,
            "win_rate": 56.5,
            "last_played_date": "2022-06-09",
        },
    ]
    # Counted on the same team only; "All-Black" played 6 games with Ammar but 4 against.
    all_black = next(peer for peer in data["peers"] if peer["account_id"] == 105236646)
    assert (all_black["games"], all_black["wins"]) == (2, 1)
    games = [peer["games"] for peer in data["peers"]]
    assert games == sorted(games, reverse=True)


async def test_peers_below_min_games_together_are_left_out(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route(opendota, "peers")

    data = await call(client, "get_player_peers", min_games=50)

    assert [peer["persona_name"] for peer in data["peers"]] == [
        "Rizoct",
        "Oira",
        "Heisenberg",
        "ダビオン",
        "1",
        "ice cream seller",
        "Iffy",
        "Lagmeister",
    ]


async def test_totals_name_each_stat_with_its_average(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route(opendota, "totals")

    data = await call(client, "get_player_totals")

    totals = {total["field"]: total for total in data["totals"]}
    assert totals["kills"] == {
        "field": "kills",
        "stat": "Kills",
        "games": 1300,
        "total": 11235,
        "average": 8.64,
        "average_mmss": None,
    }
    assert totals["gold_per_min"]["stat"] == "Gold per minute"
    assert totals["gold_per_min"]["average"] == 485.4
    assert totals["duration"]["average_mmss"] == "41:24"
    assert totals["purchase_ward_observer"]["stat"] == "Observer wards bought"
    # No games with the stat recorded: nothing to average.
    assert totals["purchase_rapier"]["average"] is None
    assert len(totals) == 29


async def test_a_new_opendota_stat_still_gets_a_readable_name(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get(f"/players/{AMMAR}").respond(json=load_fixture(f"players/{AMMAR}.json"))
    opendota.get(f"/players/{AMMAR}/totals").respond(
        json=[{"field": "wisdom_runes", "n": 4, "sum": 6}]
    )

    data = await call(client, "get_player_totals")

    assert data["totals"][0]["stat"] == "Wisdom runes"


async def test_histogram_buckets_a_stat_with_win_rates(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route(opendota, "histograms/gold_per_min")

    data = await call(client, "get_player_histogram", field="gpm")

    assert data["field"] == "gold_per_min"
    assert data["stat"] == "Gold per minute"
    assert data["games"] == 1300
    # Empty buckets at either end are trimmed; empty ones in between are kept.
    assert data["buckets"][0] == {
        "low": 96,
        "high": 120,
        "games": 2,
        "wins": 0,
        "win_rate": 0.0,
        "range_mmss": None,
    }
    assert data["buckets"][1]["games"] == 0
    assert data["buckets"][-1] == {
        "low": 912,
        "high": 936,
        "games": 1,
        "wins": 1,
        "win_rate": 100.0,
        "range_mmss": None,
    }
    assert len(data["buckets"]) == 35


async def test_duration_histogram_also_reads_as_mmss(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route(opendota, "histograms/duration")

    data = await call(client, "get_player_histogram", field="game length")

    assert data["buckets"][0]["range_mmss"] == "06:51-09:08"
    # The last bucket is as wide as the others.
    assert (data["buckets"][-1]["low"], data["buckets"][-1]["high"]) == (5343, 5480)


@pytest.mark.parametrize(
    ("asked", "field"),
    [
        ("gpm", "gold_per_min"),
        ("last hits", "last_hits"),
        ("xpm", "xp_per_min"),
        ("kda", "kda"),
        ("apm", "actions_per_min"),
        ("observer wards", "purchase_ward_observer"),
        ("Hero Damage", "hero_damage"),
    ],
)
async def test_histogram_accepts_everyday_stat_words(
    client: Client[Any], opendota: respx.MockRouter, asked: str, field: str
) -> None:
    histogram = route(opendota, f"histograms/{field}", "histogram_gold_per_min")

    data = await call(client, "get_player_histogram", field=asked)

    assert histogram.call_count == 1
    assert data["field"] == field


async def test_an_unknown_histogram_stat_fails_with_the_valid_ones(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route(opendota, "histograms/gold_per_min")

    with pytest.raises(ToolError, match=r"Unknown stat 'net worth'.*gold_per_min.*last_hits"):
        await call(client, "get_player_histogram", field="net worth")

    assert api_calls(opendota) == 0


@pytest.mark.parametrize("tool", FILTERED_TOOLS)
async def test_each_tool_passes_filters_on_and_discloses_them(
    client: Client[Any], opendota: respx.MockRouter, tool: str
) -> None:
    endpoint, arguments = FILTERED_TOOLS[tool]
    sent = route(opendota, endpoint)

    data = await call(
        client, tool, **arguments, filters={"hero": "pudge", "lane": "pos 1", "ranked_only": True}
    )

    assert sent_query(sent) == [("hero_id", "14"), ("lane_role", "1"), ("lobby_type", "7")]
    assert data["resolved_player"]["account_id"] == AMMAR
    assert data["filters"]["applied"] == ["Ranked", "safe lane (pos 1)", "playing Pudge"]
    assert data["filters"]["parsed_only_note"] == PARSED_ONLY


@pytest.mark.parametrize("tool", FILTERED_TOOLS)
async def test_each_tool_leaves_turbo_out_by_default(
    client: Client[Any], opendota: respx.MockRouter, tool: str
) -> None:
    endpoint, arguments = FILTERED_TOOLS[tool]
    sent = route(opendota, endpoint)

    data = await call(client, tool, **arguments)

    assert sent_query(sent) == []
    assert data["filters"]["game_modes"] == STANDARD_GAMES
    assert data["filters"]["applied"] == []


@pytest.mark.parametrize("tool", FILTERED_TOOLS)
async def test_each_tool_publishes_an_output_schema_and_is_read_only(
    client: Client[Any], tool: str
) -> None:
    tools = {listed.name: listed for listed in await client.list_tools()}

    listed = tools[tool]
    assert listed.annotations is not None
    assert listed.annotations.read_only_hint is True
    assert listed.output_schema is not None
    assert {"resolved_player", "filters"} <= set(listed.output_schema["properties"])
    assert "filters" in listed.input_schema["properties"]
