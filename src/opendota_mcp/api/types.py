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

PLAYER_STAT_FIELDS = (
    "kills",
    "deaths",
    "assists",
    "kda",
    "gold_per_min",
    "xp_per_min",
    "last_hits",
    "denies",
    "lane_efficiency_pct",
    "duration",
    "level",
    "hero_damage",
    "tower_damage",
    "hero_healing",
    "stuns",
    "tower_kills",
    "neutral_kills",
    "courier_kills",
    "purchase_tpscroll",
    "purchase_ward_observer",
    "purchase_ward_sentry",
    "purchase_gem",
    "purchase_rapier",
    "pings",
    "throw",
    "comeback",
    "stomp",
    "loss",
    "actions_per_min",
)
"""Stats `/players/{id}/totals` reports and `/players/{id}/histograms/{field}` has data for.
Any other histogram field silently returns `[]`."""


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


class PlayerPeerEntry(BaseModel):
    """One entry of `/players/{account_id}/peers`: someone who shared matches with the Player.

    `games`/`win` count every shared match; `with_*` only those on the same team.
    """

    account_id: int
    personaname: str | None = None
    last_played: int | None = None
    with_games: int
    with_win: int


class PlayerTotalEntry(BaseModel):
    """One entry of `/players/{account_id}/totals`: a stat summed over `n` games that record it."""

    field: str
    n: int
    sum: int | float


class HistogramEntry(BaseModel):
    """One entry of `/players/{account_id}/histograms/{field}`: games whose stat is at least `x`,
    below the next bucket's `x`. Buckets are equally wide."""

    x: int | float
    games: int
    win: int


class CountEntry(BaseModel):
    games: int
    win: int


class PlayerCounts(BaseModel):
    """`/players/{account_id}/counts`: games and wins per ID in each category.

    `lane_role` 0 is a match whose lane isn't known (not Parsed). `patch` is the patch index.
    """

    game_mode: dict[int, CountEntry]
    lobby_type: dict[int, CountEntry]
    lane_role: dict[int, CountEntry]
    region: dict[int, CountEntry]
    patch: dict[int, CountEntry]


PLAYER_MATCH_COLUMNS = (
    "hero_id",
    "start_time",
    "kills",
    "deaths",
    "assists",
    "gold_per_min",
    "xp_per_min",
)
"""Columns `/players/{id}/matches` is asked to `project`. Projecting replaces its default
columns, so every column `PlayerMatchEntry` reads beyond the always-sent ones is listed."""


class PlayerMatchEntry(BaseModel):
    """One entry of `/players/{account_id}/matches`, newest first."""

    match_id: int
    player_slot: int
    """Below 128 is Radiant."""
    radiant_win: bool | None = None
    """Null for a match with no result, such as one abandoned early."""
    duration: int
    game_mode: int
    lobby_type: int
    hero_id: int
    start_time: int
    kills: int
    deaths: int
    assists: int
    gold_per_min: int | None = None
    xp_per_min: int | None = None


class RatingEntry(BaseModel):
    """One entry of `/players/{account_id}/ratings`: the Rank tier a Player moved to, and when.

    Sent with only `time` and `rank_tier`, despite OpenDota documenting more fields.
    """

    time: datetime
    rank_tier: int | None = None


class SearchResult(BaseModel):
    """One entry of `/search`: up to 50, most similar name first, then most recently active."""

    account_id: int
    personaname: str | None = None
    avatarfull: str | None = None
    last_match_time: datetime | None = None


PLAYER = TypeAdapter(PlayerResponse)
WIN_LOSS = TypeAdapter(WinLoss)
PLAYER_HEROES = TypeAdapter(list[PlayerHeroEntry])
PLAYER_PEERS = TypeAdapter(list[PlayerPeerEntry])
PLAYER_TOTALS = TypeAdapter(list[PlayerTotalEntry])
HISTOGRAM = TypeAdapter(list[HistogramEntry])
PLAYER_COUNTS = TypeAdapter(PlayerCounts)
PLAYER_MATCHES = TypeAdapter(list[PlayerMatchEntry])
RATINGS = TypeAdapter(list[RatingEntry])
SEARCH = TypeAdapter(list[SearchResult])


class PickBan(BaseModel):
    is_pick: bool
    hero_id: int
    team: int
    """0 is Radiant, 1 is Dire."""
    order: int


class PurchaseEntry(BaseModel):
    time: int
    """Seconds from the horn; negative before it."""
    key: str
    """Internal item name."""


class MatchPlayerEntry(BaseModel):
    """One player of `/matches/{match_id}`. The `*_t` and purchase fields are parsed-only."""

    player_slot: int
    """Below 128 is Radiant."""
    account_id: int | None = None
    """Null for an anonymous player."""
    personaname: str | None = None
    hero_id: int
    kills: int
    deaths: int
    assists: int
    net_worth: int | None = None
    level: int | None = None
    gold_per_min: int | None = None
    xp_per_min: int | None = None
    last_hits: int | None = None
    denies: int | None = None
    item_0: int = 0
    item_1: int = 0
    item_2: int = 0
    item_3: int = 0
    item_4: int = 0
    item_5: int = 0
    """Inventory item IDs; 0 is an empty slot."""
    backpack_0: int | None = 0
    backpack_1: int | None = 0
    backpack_2: int | None = 0
    item_neutral: int | None = 0
    gold_t: list[int] | None = None
    """Total gold earned by each minute."""
    xp_t: list[int] | None = None
    lh_t: list[int] | None = None
    dn_t: list[int] | None = None
    purchase_log: list[PurchaseEntry] | None = None


class ObjectiveEntry(BaseModel):
    """One entry of a match's `objectives`: first blood, buildings, Roshan, couriers, ..."""

    time: int
    type: str
    """e.g. `building_kill`, `CHAT_MESSAGE_ROSHAN_KILL`."""
    player_slot: int | None = None
    """The player credited, when there is one."""
    team: int | None = None
    """2 is Radiant, 3 is Dire: who killed Roshan or a Tormentor, or whose courier was lost."""
    key: str | int | None = None
    """For `building_kill`, the building, e.g. `npc_dota_goodguys_tower1_bot`."""
    unit: str | None = None
    """For `building_kill`, what destroyed it, e.g. `npc_dota_hero_jakiro`."""
    killer: int | None = None
    """For a courier kill, the killer's player slot; -1 when no player."""


class TeamfightPlayerEntry(BaseModel):
    deaths: int = 0
    buybacks: int = 0
    damage: int = 0
    healing: int = 0
    gold_delta: int = 0
    xp_delta: int = 0
    killed: dict[str, int] = {}
    """Unit (e.g. `npc_dota_hero_tusk`) → kills."""


class TeamfightEntry(BaseModel):
    start: int
    end: int
    deaths: int
    players: list[TeamfightPlayerEntry]
    """In player order: Radiant's five, then Dire's."""


class ChatEntry(BaseModel):
    time: int
    type: str
    """`chat` for typed text, `chatwheel` for a chat wheel line."""
    key: str | int
    """The text typed, or the chat wheel line's ID."""
    player_slot: int | None = None


class OdData(BaseModel):
    has_parsed: bool = False


class MatchResponse(BaseModel):
    """`/matches/{match_id}`. Teamfights, objectives, chat and graphs need a Parsed match."""

    match_id: int
    radiant_win: bool | None = None
    duration: int
    start_time: int
    game_mode: int
    lobby_type: int
    patch: int | None = None
    region: int | None = None
    radiant_score: int | None = None
    dire_score: int | None = None
    picks_bans: list[PickBan] | None = None
    players: list[MatchPlayerEntry]
    objectives: list[ObjectiveEntry] | None = None
    teamfights: list[TeamfightEntry] | None = None
    chat: list[ChatEntry] | None = None
    radiant_gold_adv: list[int] | None = None
    radiant_xp_adv: list[int] | None = None
    version: int | None = None
    """OpenDota's parser version; set only once the replay is parsed."""
    od_data: OdData | None = None

    @property
    def parsed(self) -> bool:
        if self.od_data is not None:
            return self.od_data.has_parsed
        return self.version is not None


MATCH = TypeAdapter(MatchResponse)
