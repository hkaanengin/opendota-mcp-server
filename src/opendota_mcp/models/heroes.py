from typing import Literal

from pydantic import BaseModel, Field

from opendota_mcp.api.types import BenchmarkRole

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


class HeroMeta(BaseModel):
    hero: str
    picks: int = Field(description="Public games the hero was played in.")
    win_rate: float | None = Field(description="Percent of those games won; null with none.")
    pro_picks: int = Field(description="Picks in recent Pro matches.")
    pro_bans: int = Field(description="Bans in recent Pro matches.")
    pro_win_rate: float | None = Field(
        description="Percent of recent Pro matches won; null with no pro picks."
    )


class HeroMetaResult(BaseModel):
    rank_bracket: str = Field(
        description='The Rank bracket counted, or "All public matches", which also counts '
        "matches without a known average medal."
    )
    heroes: list[HeroMeta] = Field(description="Highest public win rate first.")
    note: str = Field(description="Where the numbers come from; relay it.")


DataSource = Literal["Pro matches"]


class HeroMatchup(BaseModel):
    opponent: str
    games: int = Field(description="Pro matches the hero played against this opponent.")
    win_rate: float | None = Field(description="Percent of those the hero won.")


class HeroMatchupsResult(BaseModel):
    hero: str
    data_source: DataSource
    note: str = Field(description="Where the numbers come from; relay it.")
    matchups: list[HeroMatchup]


class ItemPurchases(BaseModel):
    item: str
    purchases: int = Field(description="Times bought on this hero in the Pro matches counted.")


class HeroItemPopularityResult(BaseModel):
    hero: str
    data_source: DataSource
    note: str = Field(description="Where the numbers come from; relay it.")
    start_game: list[ItemPurchases] = Field(
        description="Bought before the game started, most bought first."
    )
    early_game: list[ItemPurchases] = Field(
        description="Items costing 700+ bought in the first 10 minutes."
    )
    mid_game: list[ItemPurchases] = Field(
        description="Items costing 2000+ bought from 10 to 25 minutes."
    )
    late_game: list[ItemPurchases] = Field(
        description="Items costing 4000+ bought after 25 minutes."
    )


class BenchmarkPercentile(BaseModel):
    percentile: int = Field(description="Percent of the hero's games at or below `value`.")
    value: int | float


class HeroBenchmark(BaseModel):
    stat: str = Field(description="OpenDota's stat name, e.g. gold_per_min.")
    name: str = Field(description='How to show it, e.g. "Gold per minute".')
    percentiles: list[BenchmarkPercentile] = Field(description="Lowest percentile first.")


class HeroBenchmarksResult(BaseModel):
    hero: str
    rank_bracket: str = Field(description='The Rank bracket counted, or "All brackets".')
    role: BenchmarkRole | Literal["All roles"]
    benchmarks: list[HeroBenchmark]


class LaneGameLength(BaseModel):
    up_to: int = Field(
        description="Game length in seconds. Each row counts only games longer than the "
        "previous row's."
    )
    up_to_mmss: str = Field(description='The same as "MM:SS".')
    games: int
    win_rate: float | None = Field(description="Percent of those the hero won.")


class LanePerformance(BaseModel):
    lane: str
    games: int
    win_rate: float | None = Field(description="Percent of those the hero won; null with no games.")
    by_game_length: list[LaneGameLength] = Field(description="Shortest games first.")


class HeroLanePerformanceResult(BaseModel):
    hero: str
    note: str = Field(description="Where the numbers come from; relay it.")
    lane_note: str | None = Field(
        description="How the lane was applied, e.g. a Position mapped to its Lane; relay it. "
        "Null when every Lane is shown."
    )
    lanes: list[LanePerformance]


class HeroItemTiming(BaseModel):
    bought_by: int = Field(
        description="Game time in seconds. Each row counts only purchases after the previous "
        "row's time."
    )
    bought_by_mmss: str = Field(description='The same as "MM:SS".')
    games: int
    win_rate: float | None = Field(description="Percent of those the hero won.")


class HeroItemTimingsResult(BaseModel):
    hero: str
    item: str
    note: str = Field(description="Where the numbers come from; relay it.")
    timings: list[HeroItemTiming] = Field(description="Earliest purchases first.")


class HeroDurationBucket(BaseModel):
    start: int = Field(description="Shortest game counted, in seconds.")
    start_mmss: str
    end: int = Field(description="Games this long, in seconds, count in the next bucket.")
    end_mmss: str
    games: int
    win_rate: float | None = Field(description="Percent of those the hero won.")


class HeroDurationPerformanceResult(BaseModel):
    hero: str
    data_source: DataSource
    note: str = Field(description="Where the numbers come from; relay it.")
    durations: list[HeroDurationBucket] = Field(description="Shortest games first.")
