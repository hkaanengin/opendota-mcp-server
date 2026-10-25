from typing import Literal

from pydantic import BaseModel, Field

Number = int | float
PrimaryAttribute = Literal["Strength", "Agility", "Intelligence", "Universal"]


class HeroAttributes(BaseModel):
    """Base attributes at level 1, and how much each grows per level."""

    strength: Number
    strength_gain: Number
    agility: Number
    agility_gain: Number
    intelligence: Number
    intelligence_gain: Number


class HeroStats(BaseModel):
    base_health: Number = Field(description="Health before attributes; strength adds to it.")
    base_health_regen: Number | None
    base_mana: Number = Field(description="Mana before attributes; intelligence adds to it.")
    base_mana_regen: Number | None
    base_armor: Number
    base_magic_resistance: Number = Field(description="Percent.")
    attack_damage_min: Number
    attack_damage_max: Number
    attack_range: Number
    base_attack_time: Number = Field(description="Seconds between attacks before attack speed.")
    attack_point: Number = Field(description="Attack animation wind-up, in seconds.")
    projectile_speed: Number = Field(description="0 for melee heroes.")
    move_speed: Number
    turn_rate: Number | None
    day_vision: Number
    night_vision: Number


class AghanimsUpgrade(BaseModel):
    ability: str = Field(description="The ability upgraded or granted.")
    description: str
    new_ability: bool = Field(
        description="True when it grants a new ability rather than upgrading an existing one."
    )


class HeroResult(BaseModel):
    id: int
    name: str
    primary_attribute: PrimaryAttribute
    attack_type: str = Field(description="Melee or Ranged.")
    roles: list[str]
    attributes: HeroAttributes
    stats: HeroStats
    aghanims_scepter: AghanimsUpgrade | None = Field(
        description="What Aghanim's Scepter does for this hero; null if nothing."
    )
    aghanims_shard: AghanimsUpgrade | None = Field(
        description="What Aghanim's Shard does for this hero; null if nothing."
    )
    lore: str | None = Field(description="The hero's backstory; null unless asked for.")
