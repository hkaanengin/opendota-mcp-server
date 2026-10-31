"""`get_hero_meta`, `get_hero_matchups`, `get_hero_item_popularity` and `get_hero_benchmarks`.

Recorded from OpenDota on 2026-10-27. `heroes/heroStats.json` keeps five of the heroes
(Anti-Mage, Axe, Pudge, Invoker, Rubick) as they were recorded.
"""

from typing import Any

import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import FakeClock, api_calls, load_fixture

MEDALS = ("Herald", "Guardian", "Crusader", "Archon", "Legend", "Ancient", "Divine", "Immortal")


async def call(client: Client[Any], tool: str, **arguments: Any) -> dict[str, Any]:
    result = await client.call_tool(tool, arguments)
    assert result.structured_content is not None
    return result.structured_content


def hero_stats(opendota: respx.MockRouter) -> respx.Route:
    return opendota.get("/heroStats").respond(json=load_fixture("heroes/heroStats.json"))


async def test_meta_defaults_to_all_brackets_with_pro_picks_and_bans(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    hero_stats(opendota)

    data = await call(client, "get_hero_meta")

    # Every significant non-Turbo public match, including those without an average medal.
    assert data["rank_bracket"] == "All public matches"
    anti_mage = next(hero for hero in data["heroes"] if hero["hero"] == "Anti-Mage")
    assert anti_mage == {
        "hero": "Anti-Mage",
        "picks": 696499,
        "win_rate": 51.1,
        "pro_picks": 13,
        "pro_bans": 36,
        "pro_win_rate": 53.8,
    }
    # Strongest first.
    assert [hero["hero"] for hero in data["heroes"]] == [
        "Pudge",
        "Anti-Mage",
        "Invoker",
        "Axe",
        "Rubick",
    ]


@pytest.mark.parametrize("bracket", ["divine", "Divine", " DIVINE ", 7, "7"])
async def test_meta_for_one_rank_bracket_by_medal_name_or_number(
    client: Client[Any], opendota: respx.MockRouter, bracket: str | int
) -> None:
    hero_stats(opendota)

    data = await call(client, "get_hero_meta", rank_bracket=bracket)

    assert data["rank_bracket"] == "Divine"
    assert data["heroes"][0] == {
        "hero": "Invoker",
        "picks": 88352,
        "win_rate": 51.5,
        "pro_picks": 15,
        "pro_bans": 24,
        "pro_win_rate": 40.0,
    }
    anti_mage = next(hero for hero in data["heroes"] if hero["hero"] == "Anti-Mage")
    assert (anti_mage["picks"], anti_mage["win_rate"]) == (69369, 50.8)


async def test_every_bracket_is_answered_from_one_cached_request(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route = hero_stats(opendota)

    await call(client, "get_hero_meta")
    await call(client, "get_hero_meta", rank_bracket="herald")
    await call(client, "get_hero_meta", rank_bracket=5)

    assert route.call_count == 1


@pytest.mark.parametrize("bracket", ["mythic", "0", 9, "divine 4", ""])
async def test_invalid_rank_bracket_fails_listing_the_eight_medals(
    client: Client[Any], opendota: respx.MockRouter, bracket: str | int
) -> None:
    with pytest.raises(ToolError) as error:
        await call(client, "get_hero_meta", rank_bracket=bracket)

    message = str(error.value)
    assert f"Unknown rank bracket {bracket!r}" in message
    for number, medal in enumerate(MEDALS, start=1):
        assert f"{number} {medal}" in message
    assert api_calls(opendota) == 0


async def test_a_bracket_without_any_games_fails_suggesting_another(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    # OpenDota currently reports no Immortal games for any hero.
    hero_stats(opendota)

    with pytest.raises(ToolError) as error:
        await call(client, "get_hero_meta", rank_bracket="immortal")

    message = str(error.value)
    assert "no Immortal games" in message
    assert "average medal" in message
    assert "Try Divine" in message


def matchups(opendota: respx.MockRouter) -> respx.Route:
    return opendota.get("/heroes/1/matchups").respond(json=load_fixture("heroes/1_matchups.json"))


async def test_matchups_default_to_most_played_opponents_labelled_as_pro_data(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    matchups(opendota)

    data = await call(client, "get_hero_matchups", hero="am")

    assert data["hero"] == "Anti-Mage"
    assert data["data_source"] == "Pro matches"
    assert "Pro matches" in data["note"]
    assert len(data["matchups"]) == 10
    assert "fewer than 10 times are left out" in data["note"]
    assert data["matchups"][:2] == [
        {"opponent": "Storm Spirit", "games": 82, "win_rate": 50.0},
        {"opponent": "Skywrath Mage", "games": 80, "win_rate": 47.5},
    ]


async def test_matchups_best_and_worst_skip_opponents_below_min_games(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    matchups(opendota)

    best = await call(client, "get_hero_matchups", hero="Anti-Mage", sort="best", limit=3)
    worst = await call(client, "get_hero_matchups", hero="Anti-Mage", sort="worst", limit=3)

    assert best["matchups"] == [
        {"opponent": "Lifestealer", "games": 15, "win_rate": 86.7},
        {"opponent": "Outworld Devourer", "games": 14, "win_rate": 71.4},
        {"opponent": "Underlord", "games": 13, "win_rate": 69.2},
    ]
    assert [row["opponent"] for row in worst["matchups"]] == [
        "Lone Druid",
        "Weaver",
        "Alchemist",
    ]
    assert worst["matchups"][0] == {"opponent": "Lone Druid", "games": 13, "win_rate": 23.1}


async def test_matchups_min_games_can_be_lowered(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    matchups(opendota)

    data = await call(client, "get_hero_matchups", hero="Anti-Mage", min_games=1, limit=200)

    assert len(data["matchups"]) == 126
    assert {"opponent": "Bloodseeker", "games": 2, "win_rate": 50.0} in data["matchups"]


async def test_item_popularity_names_items_by_game_phase_labelled_as_pro_data(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/heroes/1/itemPopularity").respond(
        json=load_fixture("heroes/1_itemPopularity.json")
    )

    data = await call(client, "get_hero_item_popularity", hero="magina")

    assert data["hero"] == "Anti-Mage"
    assert data["data_source"] == "Pro matches"
    assert "Pro matches" in data["note"]
    assert data["start_game"][:4] == [
        {"item": "Iron Branch", "purchases": 190},
        {"item": "Circlet", "purchases": 132},
        {"item": "Tango", "purchases": 81},
        {"item": "Faerie Fire", "purchases": 78},
    ]
    # Ties are alphabetical.
    assert [row["item"] for row in data["early_game"][:3]] == [
        "Boots of Speed",
        "Ring of Health",
        "Power Treads",
    ]
    assert {"item": "Battle Fury", "purchases": 99} in data["mid_game"]
    assert len(data["late_game"]) == 33


async def test_benchmarks_give_readable_stat_percentiles_across_all_games(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route = opendota.get("/benchmarks", params={"hero_id": "1"}).respond(
        json=load_fixture("heroes/benchmarks_1.json")
    )

    data = await call(client, "get_hero_benchmarks", hero="Anti-Mage")

    assert dict(route.calls.last.request.url.params) == {"hero_id": "1"}
    assert data["hero"] == "Anti-Mage"
    assert data["rank_bracket"] == "All brackets"
    assert data["role"] == "All roles"
    gpm = next(row for row in data["benchmarks"] if row["stat"] == "gold_per_min")
    assert gpm["name"] == "Gold per minute"
    assert gpm["percentiles"][:2] == [
        {"percentile": 10, "value": 423},
        {"percentile": 20, "value": 501},
    ]
    assert [point["percentile"] for point in gpm["percentiles"]] == [
        10,
        20,
        30,
        40,
        50,
        60,
        70,
        80,
        90,
        95,
        99,
    ]
    kills = next(row for row in data["benchmarks"] if row["stat"] == "kills_per_min")
    assert kills["name"] == "Kills per minute"
    assert kills["percentiles"][0] == {"percentile": 10, "value": 0.08}
    assert len(data["benchmarks"]) == 10


async def test_benchmarks_for_one_rank_bracket_and_role(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route = opendota.get("/benchmarks").respond(
        json=load_fixture("heroes/benchmarks_1_divine_core.json")
    )

    data = await call(
        client, "get_hero_benchmarks", hero="antimage", rank_bracket="divine", role="core"
    )

    assert dict(route.calls.last.request.url.params) == {
        "hero_id": "1",
        "bracket": "7",
        "role": "core",
    }
    assert (data["rank_bracket"], data["role"]) == ("Divine", "core")
    gpm = next(row for row in data["benchmarks"] if row["stat"] == "gold_per_min")
    assert {"percentile": 50, "value": 731} in gpm["percentiles"]


async def test_benchmarks_reject_a_role_other_than_core_or_support(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    with pytest.raises(ToolError) as error:
        await call(client, "get_hero_benchmarks", hero="Anti-Mage", role="carry")

    assert "'core' or 'support'" in str(error.value)

    assert api_calls(opendota) == 0


HERO_WIDE_TOOLS = {
    "get_hero_meta": {"heroes", "rank_bracket", "note"},
    "get_hero_matchups": {"hero", "data_source", "matchups"},
    "get_hero_item_popularity": {"hero", "data_source", "start_game", "late_game"},
    "get_hero_benchmarks": {"hero", "rank_bracket", "role", "benchmarks"},
}


@pytest.mark.parametrize(("tool", "fields"), HERO_WIDE_TOOLS.items())
async def test_hero_wide_tools_publish_an_output_schema_and_are_read_only(
    client: Client[Any], tool: str, fields: set[str]
) -> None:
    tools = {listed.name: listed for listed in await client.list_tools()}

    listed = tools[tool]
    assert listed.annotations is not None
    assert listed.annotations.read_only_hint is True
    assert listed.output_schema is not None
    assert fields <= set(listed.output_schema["properties"])


@pytest.mark.parametrize(
    "tool", ["get_hero_matchups", "get_hero_item_popularity", "get_hero_benchmarks"]
)
async def test_unknown_hero_fails_with_a_suggestion_without_calling_opendota(
    client: Client[Any], opendota: respx.MockRouter, tool: str
) -> None:
    with pytest.raises(ToolError) as error:
        await call(client, tool, hero="rubek")

    assert "Rubick" in str(error.value)
    assert api_calls(opendota) == 0


HERO_WIDE_ENDPOINTS = {
    "get_hero_meta": ("/heroStats", "heroStats.json"),
    "get_hero_matchups": ("/heroes/1/matchups", "1_matchups.json"),
    "get_hero_item_popularity": ("/heroes/1/itemPopularity", "1_itemPopularity.json"),
    "get_hero_benchmarks": ("/benchmarks", "benchmarks_1.json"),
}


@pytest.mark.parametrize(("tool", "endpoint"), HERO_WIDE_ENDPOINTS.items())
async def test_hero_wide_responses_are_cached_for_six_hours(
    client: Client[Any],
    opendota: respx.MockRouter,
    clock: FakeClock,
    tool: str,
    endpoint: tuple[str, str],
) -> None:
    path, fixture = endpoint
    route = opendota.get(path).respond(json=load_fixture(f"heroes/{fixture}"))
    arguments = {} if tool == "get_hero_meta" else {"hero": "Anti-Mage"}

    await call(client, tool, **arguments)
    clock.advance(6 * 60 * 60 - 1)
    await call(client, tool, **arguments)
    assert route.call_count == 1

    clock.advance(1)
    await call(client, tool, **arguments)
    assert route.call_count == 2
