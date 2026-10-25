from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from opendota_mcp.api.types import AghsDescConstant, HeroConstant
from opendota_mcp.models import (
    AghanimsUpgrade,
    HeroAttributes,
    HeroResult,
    HeroStats,
    PrimaryAttribute,
)
from opendota_mcp.reference import ReferenceStore
from opendota_mcp.resolve import resolve_hero
from opendota_mcp.tools.annotations import READ_ONLY
from opendota_mcp.tools.descriptions import HERO

PRIMARY_ATTRIBUTES: dict[str, PrimaryAttribute] = {
    "str": "Strength",
    "agi": "Agility",
    "int": "Intelligence",
    "all": "Universal",
}


def register_hero_tools(mcp: FastMCP, references: ReferenceStore) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def get_hero(
        hero: Annotated[str | int, Field(description=HERO)],
        include_lore: Annotated[
            bool, Field(description="Also return the hero's backstory (long).")
        ] = False,
    ) -> HeroResult:
        """A hero's facts: primary attribute, roles, base stats and attributes, and what
        Aghanim's Scepter and Shard do for it.

        Use for "what does Aghs do on Pudge", "Anti-Mage's base armor", "is Lina melee".
        """
        reference = await references.current()
        found = resolve_hero(hero, reference)
        aghs = reference.aghs.get(found.id)
        return HeroResult(
            id=found.id,
            name=found.localized_name,
            primary_attribute=PRIMARY_ATTRIBUTES[found.primary_attr],
            attack_type=found.attack_type,
            roles=found.roles,
            attributes=_attributes(found),
            stats=_stats(found),
            aghanims_scepter=_scepter(aghs),
            aghanims_shard=_shard(aghs),
            lore=reference.hero_lore.get(found.internal_name) if include_lore else None,
        )


def _attributes(hero: HeroConstant) -> HeroAttributes:
    return HeroAttributes(
        strength=hero.base_str,
        strength_gain=hero.str_gain,
        agility=hero.base_agi,
        agility_gain=hero.agi_gain,
        intelligence=hero.base_int,
        intelligence_gain=hero.int_gain,
    )


def _stats(hero: HeroConstant) -> HeroStats:
    return HeroStats(
        base_health=hero.base_health,
        base_health_regen=hero.base_health_regen,
        base_mana=hero.base_mana,
        base_mana_regen=hero.base_mana_regen,
        base_armor=hero.base_armor,
        base_magic_resistance=hero.base_mr,
        attack_damage_min=hero.base_attack_min,
        attack_damage_max=hero.base_attack_max,
        attack_range=hero.attack_range,
        base_attack_time=hero.attack_rate,
        attack_point=hero.attack_point,
        projectile_speed=hero.projectile_speed,
        move_speed=hero.move_speed,
        turn_rate=hero.turn_rate,
        day_vision=hero.day_vision,
        night_vision=hero.night_vision,
    )


def _scepter(aghs: AghsDescConstant | None) -> AghanimsUpgrade | None:
    if aghs is None or not aghs.has_scepter:
        return None
    return AghanimsUpgrade(
        ability=aghs.scepter_skill_name,
        description=aghs.scepter_desc,
        new_ability=aghs.scepter_new_skill,
    )


def _shard(aghs: AghsDescConstant | None) -> AghanimsUpgrade | None:
    if aghs is None or not aghs.has_shard:
        return None
    return AghanimsUpgrade(
        ability=aghs.shard_skill_name,
        description=aghs.shard_desc,
        new_ability=aghs.shard_new_skill,
    )
