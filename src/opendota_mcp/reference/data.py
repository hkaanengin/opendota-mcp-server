"""One consistent set of hero and item reference data, with lookups by ID and internal name."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from importlib.resources import files
from typing import Any, Self

from pydantic import TypeAdapter

from opendota_mcp.api.types import (
    AGHS_DESC,
    HERO_LORE,
    HEROES,
    ITEMS,
    PATCHES,
    AghsDescConstant,
    HeroConstant,
    ItemConstant,
    PatchConstant,
)

_SNAPSHOTS = files("opendota_mcp.reference") / "snapshots"


def _snapshot(resource: str, adapter: TypeAdapter[Any]) -> Any:
    return adapter.validate_python(
        json.loads((_SNAPSHOTS / f"{resource}.json").read_text(encoding="utf-8"))
    )


@dataclass(frozen=True)
class Reference:
    """Immutable: a refresh builds a new one, so a tool call never sees a half-updated set."""

    heroes: Mapping[int, HeroConstant]
    items: Mapping[str, ItemConstant]
    """Internal item name → item."""
    aghs: Mapping[int, AghsDescConstant]
    """Hero ID → its Aghanim's Scepter and Shard upgrades."""
    hero_lore: Mapping[str, str]
    """Hero internal name → lore."""
    patches: Sequence[PatchConstant]

    @classmethod
    def bundled(cls) -> Self:
        """The snapshots shipped in the package, used until (or unless) OpenDota answers."""
        return cls.empty().with_parts(
            heroes=_snapshot("heroes", HEROES),
            items=_snapshot("items", ITEMS),
            aghs_desc=_snapshot("aghs_desc", AGHS_DESC),
            hero_lore=_snapshot("hero_lore", HERO_LORE),
            patch=_snapshot("patch", PATCHES),
        )

    @classmethod
    def empty(cls) -> Self:
        return cls(heroes={}, items={}, aghs={}, hero_lore={}, patches=())

    def with_parts(self, **parts: Any) -> Self:
        """A copy with some resources replaced, each given as its `/constants/*` payload."""
        changes: dict[str, Any] = {}
        if "heroes" in parts:
            changes["heroes"] = {hero.id: hero for hero in parts.pop("heroes").values()}
        if "items" in parts:
            changes["items"] = dict(parts.pop("items"))
        if "aghs_desc" in parts:
            changes["aghs"] = {entry.hero_id: entry for entry in parts.pop("aghs_desc")}
        if "hero_lore" in parts:
            changes["hero_lore"] = dict(parts.pop("hero_lore"))
        if "patch" in parts:
            changes["patches"] = tuple(sorted(parts.pop("patch"), key=lambda patch: patch.id))
        if parts:
            raise TypeError(f"unknown reference resources: {', '.join(parts)}")
        return replace(self, **changes)

    def hero_name(self, hero_id: int) -> str:
        """Display name, e.g. 1 → "Anti-Mage". Unknown IDs get a readable placeholder."""
        hero = self.heroes.get(hero_id)
        return hero.localized_name if hero else f"Unknown hero (id {hero_id})"

    def item_name(self, internal_name: str) -> str:
        """Display name, e.g. `black_king_bar` → "Black King Bar"; the key itself if unknown."""
        item = self.items.get(internal_name)
        return item.dname if item and item.dname else internal_name
