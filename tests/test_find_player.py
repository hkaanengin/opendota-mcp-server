from typing import Any

import respx
from fastmcp import Client

from tests.conftest import load_fixture
from tests.test_player_profile import AMMAR

SEARCH = load_fixture("search_ammar.json")
TOP_FIVE = [entry["account_id"] for entry in SEARCH[:5]]


def route_ranks(opendota: respx.MockRouter, rank_tier: int | None = 54) -> None:
    player = load_fixture(f"players/{AMMAR}.json")
    for account_id in TOP_FIVE:
        opendota.get(f"/players/{account_id}").respond(json={**player, "rank_tier": rank_tier})


async def find(client: Client[Any], name: str) -> dict[str, Any]:
    result = await client.call_tool("find_player", {"name": name})
    assert result.structured_content is not None
    return result.structured_content


async def test_candidates_carry_details_that_tell_players_apart(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/search").respond(json=SEARCH)
    route_ranks(opendota)

    data = await find(client, "Ammar")

    assert data["players_found"] == 50
    assert [c["account_id"] for c in data["candidates"]] == TOP_FIVE
    assert data["candidates"][1] == {
        "persona_name": "Ammar",
        "account_id": AMMAR,
        "exact_name_match": True,
        "avatar": "https://avatars.steamstatic.com/794da1bd73f3e00e675587b275ac0efd5077d2e0_full.jpg",
        "last_match_date": "2026-10-25",
        "rank": "Legend 4",
        "profile_url": f"https://www.opendota.com/players/{AMMAR}",
    }
    assert data["candidates"][0]["exact_name_match"] is False  # ✪AmmaR


async def test_uncalibrated_candidates_read_as_unranked(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/search").respond(json=SEARCH)
    route_ranks(opendota, rank_tier=None)

    data = await find(client, "Ammar")

    assert {c["rank"] for c in data["candidates"]} == {"Unranked"}


async def test_nobody_found_is_an_empty_list_not_an_error(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/search").respond(json=[])

    data = await find(client, "qqqqqqqqqqqqqqq")

    assert data == {"players_found": 0, "candidates": []}


async def test_searches_send_the_name_as_typed(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    search = opendota.get("/search").respond(json=[])

    await find(client, "Tom & Jerry #1+")

    assert search.calls.last.request.url.params["q"] == "Tom & Jerry #1+"


async def test_a_candidate_opendota_has_no_profile_for_is_left_out(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/search").respond(json=SEARCH)
    route_ranks(opendota)
    opendota.get(f"/players/{TOP_FIVE[0]}").respond(404, json={"error": "Not Found"})

    data = await find(client, "Ammar")

    assert [c["account_id"] for c in data["candidates"]] == TOP_FIVE[1:]
