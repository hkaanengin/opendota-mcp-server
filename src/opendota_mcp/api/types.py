"""OpenDota response shapes, as OpenDota sends them (IDs, epoch seconds)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, TypeAdapter

RECORD_FIELDS = (
    "kills",
    "deaths",
    "assists",
    "gold_per_min",
    "xp_per_min",
    "last_hits",
    "denies",
    "hero_damage",
    "tower_damage",
    "hero_healing",
    "duration",
)
"""Stats `/records/{field}` has data for. Any other field silently returns `[]`."""


class RecordEntry(BaseModel):
    match_id: int
    start_time: int
    hero_id: int
    score: int | float


class HeroConstant(BaseModel):
    """One entry of `/constants/heroes`, keyed there by hero ID."""

    id: int
    name: str
    """Internal name with its prefix, e.g. `npc_dota_hero_antimage`."""
    localized_name: str
    primary_attr: Literal["str", "agi", "int", "all"]
    """`all` is Universal."""
    attack_type: str
    roles: list[str]
    base_health: int | float
    base_health_regen: int | float | None
    base_mana: int | float
    base_mana_regen: int | float | None
    base_armor: int | float
    base_mr: int | float
    base_attack_min: int | float
    base_attack_max: int | float
    base_str: int | float
    base_agi: int | float
    base_int: int | float
    str_gain: int | float
    agi_gain: int | float
    int_gain: int | float
    attack_range: int | float
    projectile_speed: int | float
    attack_rate: int | float
    """Base attack time in seconds."""
    attack_point: int | float
    move_speed: int | float
    turn_rate: int | float | None
    day_vision: int | float
    night_vision: int | float

    @property
    def internal_name(self) -> str:
        """The name without its prefix, e.g. `antimage`: the key of `/constants/hero_lore`."""
        return self.name.removeprefix("npc_dota_hero_")


class ItemAbilityConstant(BaseModel):
    type: str
    title: str
    description: str


class ItemAttribConstant(BaseModel):
    key: str
    value: str
    display: str | None = None
    """A label with a `{value}` placeholder, e.g. `+ {value} Strength`. Unset for values
    that only feed other text, such as durations."""


class ItemConstant(BaseModel):
    """One entry of `/constants/items`, keyed there by internal name (e.g. `black_king_bar`)."""

    id: int
    dname: str | None = None
    """Display name. A few internal-only items have none."""
    cost: int | None = None
    abilities: list[ItemAbilityConstant] | None = None
    attrib: list[ItemAttribConstant] | None = None
    cd: int | float | bool | None = None
    """Cooldown in seconds; `false` when the item has none."""
    mc: int | float | bool | None = None
    """Mana cost; `false` when the item has none."""
    notes: str | None = None
    lore: str | None = None
    components: list[str] | None = None


class AghsDescConstant(BaseModel):
    """One entry of `/constants/aghs_desc`: a hero's Aghanim's Scepter and Shard upgrades."""

    hero_id: int
    has_scepter: bool
    scepter_desc: str
    scepter_skill_name: str
    scepter_new_skill: bool
    has_shard: bool
    shard_desc: str
    shard_skill_name: str
    shard_new_skill: bool


class PatchConstant(BaseModel):
    """One entry of `/constants/patch`. `id` is the index the player filter `patch` takes."""

    id: int
    name: str
    """Version, e.g. `7.39`."""
    date: datetime


HEROES = TypeAdapter(dict[str, HeroConstant])
ITEMS = TypeAdapter(dict[str, ItemConstant])
AGHS_DESC = TypeAdapter(list[AghsDescConstant])
HERO_LORE = TypeAdapter(dict[str, str])
"""Hero internal name (e.g. `antimage`) → lore."""
PATCHES = TypeAdapter(list[PatchConstant])


class PlayerProfile(BaseModel):
    account_id: int
    personaname: str | None = None
    avatarfull: str | None = None


class PlayerResponse(BaseModel):
    """`/players/{account_id}`."""

    profile: PlayerProfile
    rank_tier: int | None = None
    """Medal and stars as two digits, e.g. 74 = Divine 4; null when uncalibrated."""
    leaderboard_rank: int | None = None
    """Set for Immortal players on the leaderboard."""


class WinLoss(BaseModel):
    """`/players/{account_id}/wl`."""

    win: int
    lose: int


class PlayerHeroEntry(BaseModel):
    """One entry of `/players/{account_id}/heroes`."""

    hero_id: int
    games: int
    win: int


class SearchResult(BaseModel):
    """One entry of `/search`: up to 50, most similar name first, then most recently active."""

    account_id: int
    personaname: str | None = None
    avatarfull: str | None = None
    last_match_time: datetime | None = None


PLAYER = TypeAdapter(PlayerResponse)
WIN_LOSS = TypeAdapter(WinLoss)
PLAYER_HEROES = TypeAdapter(list[PlayerHeroEntry])
SEARCH = TypeAdapter(list[SearchResult])
