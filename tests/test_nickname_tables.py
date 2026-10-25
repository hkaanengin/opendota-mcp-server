"""Data checks: the Nickname tables agree with the bundled hero and item data."""

import re
import tomllib
from collections import defaultdict
from importlib.resources import files
from typing import Any

import pytest

from tests.conftest import bundled_constants

TABLES = files("opendota_mcp.resolve") / "nicknames"


def load_table(name: str) -> dict[str, Any]:
    return tomllib.loads((TABLES / f"{name}.toml").read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    """How resolution compares names: case, spaces and punctuation don't matter."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def hero_names() -> dict[str, set[str]]:
    """Internal name → every name it already resolves by, without a Nickname."""
    return {
        hero["name"].removeprefix("npc_dota_hero_"): {
            normalize(hero["name"].removeprefix("npc_dota_hero_")),
            normalize(hero["localized_name"]),
        }
        for hero in bundled_constants("heroes").values()
    }


def item_names() -> dict[str, set[str]]:
    return {
        key: {normalize(key), normalize(item["dname"])}
        for key, item in bundled_constants("items").items()
        if item.get("dname")
    }


TABLE_NAMES = {"heroes": hero_names, "items": item_names}


def nicknames(table: dict[str, Any]) -> dict[str, list[str]]:
    return {key: value for key, value in table.items() if key != "ambiguous"}


@pytest.mark.parametrize("name", TABLE_NAMES)
def test_every_nickname_key_is_a_real_internal_name(name: str) -> None:
    known = TABLE_NAMES[name]()

    unknown = [key for key in nicknames(load_table(name)) if key not in known]

    assert unknown == []


@pytest.mark.parametrize("name", TABLE_NAMES)
def test_no_nickname_maps_to_two_targets(name: str) -> None:
    table = load_table(name)
    targets: dict[str, set[str]] = defaultdict(set)
    for key, values in nicknames(table).items():
        for nickname in values:
            targets[normalize(nickname)].add(key)
    for nickname in table.get("ambiguous", {}):
        targets[normalize(nickname)].add("[ambiguous]")

    clashes = {nickname: keys for nickname, keys in targets.items() if len(keys) > 1}

    assert clashes == {}


@pytest.mark.parametrize("name", TABLE_NAMES)
def test_no_nickname_is_already_a_real_name(name: str) -> None:
    """A Nickname equal to a real name would be dead (exact names win) or misleading."""
    real = set().union(*TABLE_NAMES[name]().values())
    table = load_table(name)
    every = [n for values in nicknames(table).values() for n in values]
    every += list(table.get("ambiguous", {}))

    assert [nickname for nickname in every if normalize(nickname) in real] == []


def test_ambiguous_hero_nicknames_list_real_heroes() -> None:
    known = hero_names()
    for nickname, candidates in load_table("heroes")["ambiguous"].items():
        assert len(candidates) > 1, nickname
        assert [c for c in candidates if c not in known] == [], nickname
