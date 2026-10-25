"""`get_player_win_loss` and the shared player `filters` every player stat tool takes.

Each filter is checked by the exact query OpenDota receives, so a filter that silently
stops reaching OpenDota fails here rather than skewing someone's stats.
"""

from typing import Any

import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import api_calls, load_fixture
from tests.test_player_profile import AMMAR

FRIEND = 87278757
STANDARD_GAMES = (
    "Standard games only: Turbo, other non-standard modes and games shorter than 6 minutes "
    'are left out. Set game_mode to "turbo" to count Turbo.'
)
PARSED_ONLY = (
    "Lane is only known for parsed matches, so unparsed games are left out of these numbers."
)


def route_win_loss(opendota: respx.MockRouter) -> respx.Route:
    opendota.get(f"/players/{AMMAR}").respond(json=load_fixture(f"players/{AMMAR}.json"))
    return opendota.get(f"/players/{AMMAR}/wl").respond(
        json=load_fixture(f"players/{AMMAR}_wl.json")
    )


def route_friend(opendota: respx.MockRouter) -> None:
    opendota.get(f"/players/{FRIEND}").respond(
        json={"profile": {"account_id": FRIEND, "personaname": "Friend"}}
    )


def sent_query(route: respx.Route) -> list[tuple[str, str]]:
    """The query string of the route's latest request, as sorted (key, value) pairs."""
    return sorted(route.calls.last.request.url.params.multi_items())


async def win_loss(client: Client[Any], filters: dict[str, Any] | None = None) -> dict[str, Any]:
    arguments: dict[str, Any] = {"player": AMMAR}
    if filters is not None:
        arguments["filters"] = filters
    result = await client.call_tool("get_player_win_loss", arguments)
    assert result.structured_content is not None
    return result.structured_content


async def test_unfiltered_win_loss_counts_standard_games(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    wl = route_win_loss(opendota)

    data = await win_loss(client)

    assert data["resolved_player"] == {"account_id": AMMAR, "persona_name": "Ammar"}
    assert (data["wins"], data["losses"], data["win_rate"]) == (728, 572, 56.0)
    assert data["filters"] == {
        "applied": [],
        "game_modes": STANDARD_GAMES,
        "lane_note": None,
        "parsed_only_note": None,
    }
    # OpenDota's own default (significant=1) is what leaves Turbo out.
    assert sent_query(wl) == []


@pytest.mark.parametrize(
    ("filters", "query", "applied"),
    [
        ({"limit": 20}, [("limit", "20")], ["latest 20 matches"]),
        (
            {"limit": 20, "offset": 10},
            [("limit", "20"), ("offset", "10")],
            ["latest 20 matches", "skipping the latest 10"],
        ),
        ({"days": 30}, [("date", "30")], ["last 30 days"]),
        ({"days": "last 30 days"}, [("date", "30")], ["last 30 days"]),
        ({"days": "past 2 weeks"}, [("date", "14")], ["last 14 days"]),
        ({"days": "last month"}, [("date", "30")], ["last 30 days"]),
        ({"days": "today"}, [("date", "1")], ["last 1 day"]),
        # The fake clock reads 1970-01-12 13:46 UTC: 11.6 days into the month, so 12.
        ({"days": "this month"}, [("date", "12")], ["this month (last 12 days)"]),
        ({"days": "this year"}, [("date", "12")], ["this year (last 12 days)"]),
        ({"patch": "7.39"}, [("patch", "58")], ["patch 7.39"]),
        ({"patch": "Patch 7.39c"}, [("patch", "58")], ["patch 7.39"]),
        ({"patch": 7.4}, [("patch", "59")], ["patch 7.40"]),
        ({"patch": "this patch"}, [("patch", "60")], ["patch 7.41"]),
        ({"patch": "previous patch"}, [("patch", "59")], ["patch 7.40"]),
        ({"game_mode": "ranked"}, [("lobby_type", "7")], ["Ranked"]),
        ({"ranked_only": True}, [("lobby_type", "7")], ["Ranked"]),
        ({"game_mode": "unranked"}, [("lobby_type", "0")], ["Unranked"]),
        ({"game_mode": "All Pick"}, [("game_mode", "22")], ["All Pick"]),
        (
            {"game_mode": "all pick", "ranked_only": True},
            [("game_mode", "22"), ("lobby_type", "7")],
            ["Ranked", "All Pick"],
        ),
        (
            {"game_mode": "ranked all pick"},
            [("game_mode", "22"), ("lobby_type", "7")],
            ["Ranked", "All Pick"],
        ),
        (
            {"game_mode": "turbo"},
            [("game_mode", "23"), ("significant", "0")],
            ["Turbo"],
        ),
        (
            {"game_mode": "ability draft"},
            [("game_mode", "18"), ("significant", "0")],
            ["Ability Draft"],
        ),
        ({"lane": "safe lane"}, [("lane_role", "1")], ["safe lane"]),
        ({"lane": "mid"}, [("lane_role", "2")], ["mid lane"]),
        ({"lane": "offlane"}, [("lane_role", "3")], ["off lane"]),
        ({"lane": "jungle"}, [("lane_role", "4")], ["jungle"]),
        ({"lane": "pos 1"}, [("lane_role", "1")], ["safe lane (pos 1)"]),
        ({"lane": "carry"}, [("lane_role", "1")], ["safe lane (pos 1)"]),
        ({"lane": "Position 5"}, [("lane_role", "1")], ["safe lane (pos 5)"]),
        ({"lane": 4}, [("lane_role", "3")], ["off lane (pos 4)"]),
        ({"lane": "soft support"}, [("lane_role", "3")], ["off lane (pos 4)"]),
        ({"hero": "pudge"}, [("hero_id", "14")], ["playing Pudge"]),
        ({"hero": 14}, [("hero_id", "14")], ["playing Pudge"]),
        (
            {"with_heroes": ["CM"], "against_heroes": ["PA", "pudge"]},
            [("against_hero_id", "14"), ("against_hero_id", "44"), ("with_hero_id", "5")],
            [
                "with Crystal Maiden on their team",
                "against Phantom Assassin and Pudge",
            ],
        ),
        ({"with_heroes": "rylai"}, [("with_hero_id", "5")], ["with Crystal Maiden on their team"]),
        (
            {"included_players": [FRIEND]},
            [("included_account_id", str(FRIEND))],
            [f"with Friend ({FRIEND}) in the match"],
        ),
        (
            {"excluded_players": str(FRIEND)},
            [("excluded_account_id", str(FRIEND))],
            [f"without Friend ({FRIEND}) in the match"],
        ),
    ],
)
async def test_each_filter_becomes_its_opendota_query_parameter(
    client: Client[Any],
    opendota: respx.MockRouter,
    filters: dict[str, Any],
    query: list[tuple[str, str]],
    applied: list[str],
) -> None:
    wl = route_win_loss(opendota)
    route_friend(opendota)

    data = await win_loss(client, filters)

    assert sent_query(wl) == query
    assert data["filters"]["applied"] == applied


async def test_all_filters_combine_into_one_query(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    wl = route_win_loss(opendota)

    await win_loss(
        client,
        {"hero": "Pudge", "patch": "this patch", "lane": "pos 1", "days": 30, "ranked_only": True},
    )

    assert sent_query(wl) == [
        ("date", "30"),
        ("hero_id", "14"),
        ("lane_role", "1"),
        ("lobby_type", "7"),
        ("patch", "60"),
    ]


async def test_turbo_is_counted_only_when_asked_for(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route_win_loss(opendota)

    default = await win_loss(client)
    turbo = await win_loss(client, {"game_mode": "turbo"})

    assert "Turbo" in default["filters"]["game_modes"]
    assert "left out" in default["filters"]["game_modes"]
    assert turbo["filters"]["game_modes"] == "Turbo games only."


@pytest.mark.parametrize(
    ("filters", "game_modes"),
    [
        (
            {"ranked_only": True},
            "Ranked games only. Turbo, other non-standard modes and games shorter than "
            "6 minutes are left out.",
        ),
        (
            {"game_mode": "all pick", "ranked_only": True},
            "Ranked All Pick games only. Turbo, other non-standard modes and games shorter "
            "than 6 minutes are left out.",
        ),
        ({"game_mode": "ability draft"}, "Ability Draft games only."),
    ],
)
async def test_disclosure_says_which_game_modes_were_counted(
    client: Client[Any], opendota: respx.MockRouter, filters: dict[str, Any], game_modes: str
) -> None:
    route_win_loss(opendota)

    assert (await win_loss(client, filters))["filters"]["game_modes"] == game_modes


@pytest.mark.parametrize(
    ("lane", "note"),
    [
        (
            "pos 1",
            "Filtered by safe lane, where pos 1 plays. OpenDota doesn't record positions, "
            "so pos 1 and pos 5 can't be told apart.",
        ),
        (
            "hard support",
            "Filtered by safe lane, where pos 5 plays. OpenDota doesn't record positions, "
            "so pos 1 and pos 5 can't be told apart.",
        ),
        (
            "pos 3",
            "Filtered by off lane, where pos 3 plays. OpenDota doesn't record positions, "
            "so pos 3 and pos 4 can't be told apart.",
        ),
        ("pos 2", "Filtered by mid lane, where pos 2 plays."),
        ("safelane", "Filtered by safe lane."),
    ],
)
async def test_a_lane_filter_explains_its_mapping_and_that_it_covers_parsed_matches_only(
    client: Client[Any], opendota: respx.MockRouter, lane: str, note: str
) -> None:
    route_win_loss(opendota)

    data = await win_loss(client, {"lane": lane})

    assert data["filters"]["lane_note"] == note
    assert data["filters"]["parsed_only_note"] == PARSED_ONLY


@pytest.mark.parametrize(
    ("filters", "message"),
    [
        ({"patch": "6.12"}, r"Unknown patch '6\.12'\. Use a version such as 7\.41, 7\.40"),
        ({"patch": "next patch"}, r'or "this patch"'),
        ({"days": "someday"}, r"Unknown date window 'someday'.*\"this month\""),
        ({"days": 0}, r"Unknown date window 0"),
        ({"game_mode": "battle royale"}, r"Unknown game mode 'battle royale'.*ranked.*turbo"),
        (
            {"game_mode": "unranked", "ranked_only": True},
            r"ranked_only can't be combined with game_mode 'unranked'",
        ),
        ({"lane": "support"}, r"'support' could be pos 4 \(off lane\) or pos 5 \(safe lane\)"),
        ({"lane": "top"}, r"Unknown lane 'top'.*safe lane.*pos 1"),
        ({"lane": 6}, r"Unknown lane 6"),
        ({"hero": "xyzzy"}, r"No hero matches"),
        ({"against_heroes": ["phantom"]}, r"could mean"),
    ],
)
async def test_invalid_filters_fail_with_the_valid_options(
    client: Client[Any], opendota: respx.MockRouter, filters: dict[str, Any], message: str
) -> None:
    wl = route_win_loss(opendota)

    with pytest.raises(ToolError, match=message):
        await win_loss(client, filters)

    assert wl.call_count == 0


async def test_an_unknown_teammate_fails_like_an_unknown_player(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route_win_loss(opendota)
    opendota.get("/players/42").respond(404)

    with pytest.raises(ToolError, match="No player with account ID 42"):
        await win_loss(client, {"included_players": [42]})


async def test_different_filters_each_reach_opendota_and_repeats_are_cached(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    wl = route_win_loss(opendota)

    await win_loss(client, {"hero": "pudge"})
    await win_loss(client, {"hero": "anti-mage"})
    await win_loss(client, {"hero": "Pudge"})
    await win_loss(client, {"against_heroes": ["pa", "cm"]})
    await win_loss(client, {"against_heroes": ["cm", "pa"]})

    assert wl.call_count == 3
    assert api_calls(opendota) == 4  # plus the profile lookup behind the resolved player


async def test_win_rate_is_null_with_no_games(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get(f"/players/{AMMAR}").respond(json=load_fixture(f"players/{AMMAR}.json"))
    opendota.get(f"/players/{AMMAR}/wl").respond(json={"win": 0, "lose": 0})

    data = await win_loss(client, {"hero": "pudge"})

    assert (data["wins"], data["losses"], data["win_rate"]) == (0, 0, None)


async def test_win_loss_publishes_an_output_schema_and_is_read_only(client: Client[Any]) -> None:
    tools = {listed.name: listed for listed in await client.list_tools()}

    listed = tools["get_player_win_loss"]
    assert listed.annotations is not None
    assert listed.annotations.read_only_hint is True
    assert listed.output_schema is not None
    assert {"resolved_player", "wins", "losses", "win_rate", "filters"} <= set(
        listed.output_schema["properties"]
    )
    assert "filters" in listed.input_schema["properties"]
