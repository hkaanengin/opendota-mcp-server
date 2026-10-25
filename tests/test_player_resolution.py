"""How a `player` argument becomes the Resolved player, seen through `get_player_profile`."""

from typing import Any

import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import Connect, api_calls, load_fixture
from tests.test_player_profile import AMMAR, profile, route_player


async def test_a_numeric_string_is_an_account_id(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    route_player(opendota)

    data = await profile(client, str(AMMAR))

    assert data["resolved_player"]["account_id"] == AMMAR


@pytest.mark.parametrize("asked", ["me", "Me", " ME "])
async def test_a_configured_alias_skips_search_whatever_its_case(
    connect: Connect, opendota: respx.MockRouter, asked: str
) -> None:
    route_player(opendota)
    search = opendota.get("/search")

    async with connect(opendota_player_aliases=f"me={AMMAR}") as client:
        data = await profile(client, asked)

    assert data["resolved_player"] == {"account_id": AMMAR, "persona_name": "Ammar"}
    assert search.call_count == 0


async def test_no_aliases_are_configured_by_default(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/search").respond(json=[])

    with pytest.raises(ToolError, match="No player"):
        await profile(client, "me")

    assert api_calls(opendota) == 1


def search_entry(account_id: int, name: str, last_match: str | None = None) -> dict[str, Any]:
    """One `/search` row, shaped like the recorded ones."""
    return {
        "account_id": account_id,
        "avatarfull": f"https://avatars.steamstatic.com/{account_id}_full.jpg",
        "personaname": name,
        "last_match_time": last_match,
        "sml": 1,
    }


async def test_a_name_with_one_exact_match_is_used(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/search").respond(
        json=[search_entry(AMMAR, "ammar"), search_entry(14370344, "✪AmmaR")]
    )
    route_player(opendota)

    data = await profile(client, "Ammar")

    assert data["resolved_player"] == {"account_id": AMMAR, "persona_name": "ammar"}


async def test_a_name_several_players_share_fails_with_candidates_instead_of_guessing(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/search").respond(json=load_fixture("search_ammar.json"))

    with pytest.raises(ToolError) as error:
        await profile(client, "Ammar")

    message = str(error.value)
    assert message.startswith("Several players are named 'Ammar'")
    assert "Ammar (account ID 194734903, last played 2026-10-25)" in message
    assert "AMMAR (account ID 168402979" in message
    assert "account ID 14370344" not in message  # ✪AmmaR is a different name
    assert "account ID" in message.split(". ")[-1]
    assert api_calls(opendota) == 1


async def test_a_name_without_an_exact_match_lists_the_closest_players(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/search").respond(
        json=[search_entry(14370344, "✪AmmaR"), search_entry(5, "Ammar00")]
    )

    with pytest.raises(ToolError) as error:
        await profile(client, "Ammar")

    message = str(error.value)
    assert message.startswith("No player is named exactly 'Ammar'")
    assert "✪AmmaR (account ID 14370344)" in message
    assert "Ammar00 (account ID 5)" in message


async def test_a_name_nobody_has_asks_for_the_account_id(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/search").respond(json=[])

    with pytest.raises(ToolError, match="Ask for their account ID"):
        await profile(client, "zz")


@pytest.mark.parametrize("name", ["Tom&Jerry", "#1 carry", "a+b=c", "Kürlo", "Дмитрий", "鬼神"])
async def test_names_with_symbols_and_non_latin_letters_are_searched_as_typed(
    client: Client[Any], opendota: respx.MockRouter, name: str
) -> None:
    search = opendota.get("/search").respond(json=[search_entry(AMMAR, name)])
    route_player(opendota)

    data = await profile(client, name)

    assert search.calls.last.request.url.params["q"] == name
    assert data["resolved_player"] == {"account_id": AMMAR, "persona_name": name}


async def test_an_account_id_opendota_does_not_know_fails_clearly(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/players/4294967294").respond(404, json={"error": "Not Found"})

    with pytest.raises(ToolError, match="No player with account ID 4294967294"):
        await profile(client, 4294967294)
