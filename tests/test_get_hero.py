"""`get_hero`, and hero resolution by name, ID, Nickname and spelling."""

from typing import Any

import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import api_calls


async def get_hero(client: Client[Any], hero: str | int, **args: Any) -> dict[str, Any]:
    result = await client.call_tool("get_hero", {"hero": hero, **args})
    assert result.structured_content is not None
    return result.structured_content


async def test_get_hero_returns_stats_roles_and_aghanims_upgrades(client: Client[Any]) -> None:
    hero = await get_hero(client, "Anti-Mage")

    assert hero["id"] == 1
    assert hero["name"] == "Anti-Mage"
    assert hero["primary_attribute"] == "Agility"
    assert hero["attack_type"] == "Melee"
    assert hero["roles"] == ["Carry", "Escape", "Nuker"]
    assert hero["attributes"] == {
        "strength": 21,
        "strength_gain": 1.6,
        "agility": 24,
        "agility_gain": 2.8,
        "intelligence": 12,
        "intelligence_gain": 1.8,
    }
    assert hero["stats"]["move_speed"] == 310
    assert hero["stats"]["attack_range"] == 150
    assert hero["stats"]["base_attack_time"] == 1.4
    assert hero["aghanims_scepter"]["ability"] == "Blink"
    assert "Mana Break" in hero["aghanims_scepter"]["description"]
    assert hero["aghanims_scepter"]["new_ability"] is False
    assert hero["aghanims_shard"]["ability"] == "Counterspell"
    assert hero["lore"] is None


async def test_lore_is_included_only_when_asked(client: Client[Any]) -> None:
    hero = await get_hero(client, "Anti-Mage", include_lore=True)

    assert hero["lore"] is not None
    assert hero["lore"].startswith("The monks of Turstarkuri")


@pytest.mark.parametrize(
    ("asked", "name"),
    [
        ("anti-mage", "Anti-Mage"),
        ("ANTI MAGE", "Anti-Mage"),
        ("antimage", "Anti-Mage"),
        (1, "Anti-Mage"),
        ("1", "Anti-Mage"),
        ("natures prophet", "Nature's Prophet"),
        ("Wraith King", "Wraith King"),
        ("skeleton_king", "Wraith King"),
    ],
)
async def test_exact_names_internal_names_and_ids_resolve(
    client: Client[Any], asked: str | int, name: str
) -> None:
    assert (await get_hero(client, asked))["name"] == name


@pytest.mark.parametrize(
    ("asked", "name"),
    [
        ("AM", "Anti-Mage"),
        ("magina", "Anti-Mage"),
        ("wr", "Windranger"),
        ("SF", "Shadow Fiend"),
        ("ck", "Chaos Knight"),
        ("od", "Outworld Devourer"),
        ("wk", "Wraith King"),
        ("np", "Nature's Prophet"),
    ],
)
async def test_community_nicknames_resolve(client: Client[Any], asked: str, name: str) -> None:
    assert (await get_hero(client, asked))["name"] == name


@pytest.mark.parametrize(
    ("asked", "name"),
    [
        ("rubik", "Rubick"),
        ("invoeker", "Invoker"),
        ("lesrac", "Leshrac"),
        ("juggernot", "Juggernaut"),
    ],
)
async def test_misspelled_names_resolve(client: Client[Any], asked: str, name: str) -> None:
    assert (await get_hero(client, asked))["name"] == name


@pytest.mark.parametrize(
    ("asked", "candidates"),
    [
        ("es", ["Earthshaker", "Earth Spirit", "Ember Spirit"]),
        ("shadow", ["Shadow Fiend", "Shadow Shaman", "Shadow Demon"]),
    ],
)
async def test_an_ambiguous_nickname_fails_listing_the_candidates(
    client: Client[Any], asked: str, candidates: list[str]
) -> None:
    with pytest.raises(ToolError) as error:
        await client.call_tool("get_hero", {"hero": asked})

    message = str(error.value)
    assert f"{asked!r} could mean" in message
    for candidate in candidates:
        assert candidate in message


async def test_no_match_fails_with_suggestions(client: Client[Any]) -> None:
    with pytest.raises(ToolError) as error:
        await client.call_tool("get_hero", {"hero": "rubek"})

    message = str(error.value)
    assert message.startswith("No hero matches 'rubek'.")
    assert "Did you mean" in message
    assert "Rubick" in message


@pytest.mark.parametrize("asked", ["zzzzzz", "", 9999])
async def test_nothing_close_fails_saying_what_to_give(
    client: Client[Any], asked: str | int
) -> None:
    with pytest.raises(ToolError) as error:
        await client.call_tool("get_hero", {"hero": asked})

    assert str(error.value).startswith(f"No hero matches {str(asked)!r}.")


async def test_get_hero_answers_from_reference_data_without_calling_opendota(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    await get_hero(client, "pudge")

    assert api_calls(opendota) == 0


async def test_get_hero_publishes_an_output_schema_and_is_read_only(
    client: Client[Any],
) -> None:
    tool = {tool.name: tool for tool in await client.list_tools()}["get_hero"]

    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.output_schema is not None
    assert {"name", "roles", "stats", "aghanims_scepter", "aghanims_shard", "lore"} <= set(
        tool.output_schema["properties"]
    )
