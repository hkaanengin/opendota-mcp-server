"""Hero and item data: fetched live at startup, refreshed daily, bundled snapshots as fallback."""

import copy
from typing import Any

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import CONSTANTS, Connect, FakeClock, bundled_constants

DAY = 24 * 60 * 60


def with_new_hero() -> dict[str, Any]:
    """`/constants/heroes` after a patch that added a hero."""
    heroes: dict[str, Any] = copy.deepcopy(bundled_constants("heroes"))
    new = {**heroes["1"], "id": 900, "name": "npc_dota_hero_newcomer", "localized_name": "Newcomer"}
    heroes["900"] = new
    return heroes


def with_bkb_cost(cost: int) -> dict[str, Any]:
    items: dict[str, Any] = copy.deepcopy(bundled_constants("items"))
    items["black_king_bar"]["cost"] = cost
    return items


async def hero_name(client: Client[Any], hero: str) -> str:
    result = await client.call_tool("get_hero", {"hero": hero})
    assert result.structured_content is not None
    return str(result.structured_content["name"])


async def test_data_is_fetched_from_opendota_at_startup(
    connect: Connect, opendota: respx.MockRouter
) -> None:
    opendota.routes["constants/heroes"].respond(json=with_new_hero())
    opendota.routes["constants/items"].respond(json=with_bkb_cost(9999))

    async with connect() as client:
        for resource in CONSTANTS:
            assert opendota.routes[f"constants/{resource}"].call_count == 1
        assert await hero_name(client, "newcomer") == "Newcomer"
        bkb = await client.call_tool("get_item", {"item": "bkb"})

    assert bkb.structured_content is not None
    assert bkb.structured_content["cost"] == 9999


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("connection refused"),
        httpx.Response(503),
        httpx.Response(200, json=None),
        httpx.Response(200, json={"1": {"unexpected": "shape"}}),
    ],
    ids=["unreachable", "server error", "null payload", "unexpected shape"],
)
async def test_the_server_starts_on_bundled_data_when_opendota_fails(
    connect: Connect, opendota: respx.MockRouter, failure: Any
) -> None:
    for resource in CONSTANTS:
        opendota.routes[f"constants/{resource}"].mock(side_effect=[failure])

    async with connect() as client:
        assert await hero_name(client, "magina") == "Anti-Mage"
        item = await client.call_tool("get_item", {"item": "bkb"})
        assert item.structured_content is not None
        assert item.structured_content["name"] == "Black King Bar"
        with pytest.raises(ToolError):
            await hero_name(client, "newcomer")


async def test_one_failed_resource_falls_back_alone(
    connect: Connect, opendota: respx.MockRouter
) -> None:
    opendota.routes["constants/heroes"].respond(json=with_new_hero())
    opendota.routes["constants/items"].respond(503)

    async with connect() as client:
        assert await hero_name(client, "newcomer") == "Newcomer"
        item = await client.call_tool("get_item", {"item": "bkb"})

    assert item.structured_content is not None
    assert item.structured_content["cost"] == 4050


async def test_data_refreshes_every_24_hours(
    connect: Connect, opendota: respx.MockRouter, clock: FakeClock
) -> None:
    heroes = opendota.routes["constants/heroes"]

    async with connect() as client:
        heroes.respond(json=with_new_hero())
        clock.advance(DAY - 1)
        with pytest.raises(ToolError):
            await hero_name(client, "newcomer")

        clock.advance(1)
        assert await hero_name(client, "newcomer") == "Newcomer"
        await hero_name(client, "newcomer")

    assert heroes.call_count == 2


async def test_a_failed_refresh_keeps_the_data_it_had(
    connect: Connect, opendota: respx.MockRouter, clock: FakeClock
) -> None:
    heroes = opendota.routes["constants/heroes"]
    heroes.respond(json=with_new_hero())

    async with connect() as client:
        heroes.respond(503)
        clock.advance(DAY)
        assert await hero_name(client, "newcomer") == "Newcomer"


async def test_after_a_failed_fetch_it_retries_sooner_than_a_day(
    connect: Connect, opendota: respx.MockRouter, clock: FakeClock
) -> None:
    heroes = opendota.routes["constants/heroes"]
    heroes.respond(503)

    async with connect() as client:
        heroes.respond(json=with_new_hero())
        clock.advance(15 * 60)
        assert await hero_name(client, "newcomer") == "Newcomer"
