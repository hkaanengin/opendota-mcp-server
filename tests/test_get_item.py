"""`get_item`, and item resolution by name, ID, Nickname and spelling."""

from typing import Any

import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import api_calls


async def get_item(client: Client[Any], item: str | int) -> dict[str, Any]:
    result = await client.call_tool("get_item", {"item": item})
    assert result.structured_content is not None
    return result.structured_content


async def test_get_item_returns_cost_stats_and_description(client: Client[Any]) -> None:
    item = await get_item(client, "Black King Bar")

    assert item["name"] == "Black King Bar"
    assert item["cost"] == 4050
    assert item["stats"] == ["+ 10 Strength", "+ 24 Damage"]
    assert item["abilities"] == [
        {
            "kind": "active",
            "name": "Avatar",
            "description": item["abilities"][0]["description"],
        }
    ]
    assert "magic resistance" in item["abilities"][0]["description"]
    assert item["cooldown"] == 95
    assert item["mana_cost"] == 50
    assert item["components"] == ["Mithril Hammer", "Ogre Axe"]
    assert (
        item["notes"] == "Purchasing another Black King Bar will not reset its immunity duration."
    )


async def test_an_item_without_cooldown_or_components_says_so(client: Client[Any]) -> None:
    item = await get_item(client, "Aghanim's Shard")

    assert item["cost"] == 1400
    assert item["cooldown"] is None
    assert item["mana_cost"] is None
    assert item["components"] == []
    assert item["notes"] is None


@pytest.mark.parametrize(
    ("asked", "name"),
    [
        ("black king bar", "Black King Bar"),
        ("black_king_bar", "Black King Bar"),
        (116, "Black King Bar"),
        ("bkb", "Black King Bar"),
        ("BKB", "Black King Bar"),
        ("aghs shard", "Aghanim's Shard"),
        ("shard", "Aghanim's Shard"),
        ("aghs", "Aghanim's Scepter"),
        ("mkb", "Monkey King Bar"),
        ("grieves", "Guardian Greaves"),
        ("travels", "Boots of Travel"),
        ("dagon", "Dagon"),
        ("desolater", "Desolator"),
    ],
)
async def test_names_nicknames_and_typos_resolve(
    client: Client[Any], asked: str | int, name: str
) -> None:
    assert (await get_item(client, asked))["name"] == name


async def test_no_match_fails_with_suggestions(client: Client[Any]) -> None:
    with pytest.raises(ToolError) as error:
        await client.call_tool("get_item", {"item": "black king staff"})

    message = str(error.value)
    assert message.startswith("No item matches 'black king staff'. Did you mean ")
    assert "Black King Bar" in message


async def test_nothing_close_fails(client: Client[Any]) -> None:
    with pytest.raises(ToolError) as error:
        await client.call_tool("get_item", {"item": "qqqqqqq"})

    assert str(error.value).startswith("No item matches 'qqqqqqq'.")


async def test_get_item_answers_without_calling_opendota(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    await get_item(client, "bkb")

    assert api_calls(opendota) == 0


async def test_get_item_publishes_an_output_schema_and_is_read_only(
    client: Client[Any],
) -> None:
    tool = {tool.name: tool for tool in await client.list_tools()}["get_item"]

    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.output_schema is not None
    assert {"name", "cost", "stats", "abilities"} <= set(tool.output_schema["properties"])
