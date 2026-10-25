from typing import Any

import pytest
import respx
from fastmcp import Client

from tests.conftest import FakeClock, api_calls, load_fixture

AMMAR = 194734903


def route_player(opendota: respx.MockRouter, account_id: int = AMMAR, **overrides: Any) -> None:
    """The recorded `/players/{id}`, `/wl` and `/heroes` for Ammar, with profile overrides."""
    player = {**load_fixture(f"players/{AMMAR}.json"), **overrides}
    opendota.get(f"/players/{account_id}").respond(json=player)
    opendota.get(f"/players/{account_id}/wl").respond(json=load_fixture(f"players/{AMMAR}_wl.json"))
    opendota.get(f"/players/{account_id}/heroes").respond(
        json=load_fixture(f"players/{AMMAR}_heroes.json")
    )


async def profile(client: Client[Any], player: str | int) -> dict[str, Any]:
    result = await client.call_tool("get_player_profile", {"player": player})
    assert result.structured_content is not None
    return result.structured_content


async def test_profile_by_account_id_gives_rank_win_loss_and_top_heroes(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route_player(opendota)

    data = await profile(client, AMMAR)

    assert data["resolved_player"] == {"account_id": AMMAR, "persona_name": "Ammar"}
    assert data["rank"] == "Legend 4"
    assert (data["wins"], data["losses"], data["win_rate"]) == (728, 572, 56.0)
    assert [hero["hero"] for hero in data["top_heroes"]] == [
        "Nature's Prophet",
        "Juggernaut",
        "Invoker",
        "Drow Ranger",
        "Nyx Assassin",
        "Anti-Mage",
        "Dragon Knight",
        "Slark",
        "Earthshaker",
        "Mars",
    ]
    assert data["top_heroes"][0] == {
        "hero": "Nature's Prophet",
        "games": 121,
        "wins": 66,
        "win_rate": 54.5,
    }


@pytest.mark.parametrize(
    ("rank_tier", "leaderboard_rank", "shown"),
    [
        (74, None, "Divine 4"),
        (11, None, "Herald 1"),
        (70, None, "Divine"),
        (80, 412, "Immortal #412"),
        (80, None, "Immortal"),
        (None, None, "Unranked"),
        (76, None, "Unranked"),
        (5, None, "Unranked"),
        (95, None, "Unranked"),
        (87, None, "Unranked"),
    ],
)
async def test_rank_reads_as_a_medal_name(
    client: Client[Any],
    opendota: respx.MockRouter,
    rank_tier: int | None,
    leaderboard_rank: int | None,
    shown: str,
) -> None:
    route_player(opendota, rank_tier=rank_tier, leaderboard_rank=leaderboard_rank)

    assert (await profile(client, AMMAR))["rank"] == shown


async def test_player_data_is_cached_for_five_minutes(
    client: Client[Any], opendota: respx.MockRouter, clock: FakeClock
) -> None:
    route_player(opendota)

    await profile(client, AMMAR)
    assert api_calls(opendota) == 3  # profile, win/loss, heroes

    clock.advance(5 * 60 - 1)
    await profile(client, AMMAR)
    assert api_calls(opendota) == 3

    clock.advance(1)
    await profile(client, AMMAR)
    assert api_calls(opendota) == 6


async def test_a_name_search_is_cached_too(client: Client[Any], opendota: respx.MockRouter) -> None:
    search = opendota.get("/search").respond(
        json=[{"account_id": AMMAR, "personaname": "Ammar", "avatarfull": None}]
    )
    route_player(opendota)

    await profile(client, "Ammar")
    await profile(client, "Ammar")

    assert search.call_count == 1


@pytest.mark.parametrize(
    ("tool", "fields"),
    [
        ("get_player_profile", {"resolved_player", "rank", "wins", "losses", "win_rate"}),
        ("find_player", {"players_found", "candidates"}),
    ],
)
async def test_player_tools_publish_output_schemas_and_are_read_only(
    client: Client[Any], tool: str, fields: set[str]
) -> None:
    tools = {listed.name: listed for listed in await client.list_tools()}

    listed = tools[tool]
    assert listed.annotations is not None
    assert listed.annotations.read_only_hint is True
    assert listed.output_schema is not None
    assert fields <= set(listed.output_schema["properties"])
