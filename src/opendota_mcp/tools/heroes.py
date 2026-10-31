from collections.abc import Callable, Mapping
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from opendota_mcp.api import OpenDotaClient
from opendota_mcp.api.types import (
    AghsDescConstant,
    BenchmarkPoint,
    BenchmarkRole,
    HeroConstant,
    HeroLaneRoleEntry,
    HeroStatsEntry,
)
from opendota_mcp.models import (
    AghanimsUpgrade,
    BenchmarkPercentile,
    HeroAttributes,
    HeroBenchmark,
    HeroBenchmarksResult,
    HeroDurationBucket,
    HeroDurationPerformanceResult,
    HeroItemPopularityResult,
    HeroItemTiming,
    HeroItemTimingsResult,
    HeroLanePerformanceResult,
    HeroMatchup,
    HeroMatchupsResult,
    HeroMeta,
    HeroMetaResult,
    HeroResult,
    HeroStats,
    ItemPurchases,
    LaneGameLength,
    LanePerformance,
    PrimaryAttribute,
)
from opendota_mcp.models.formatting import mmss, stat_name, win_rate
from opendota_mcp.reference import Reference, ReferenceStore
from opendota_mcp.resolve import (
    LANE_NAMES,
    medal_name,
    resolve_hero,
    resolve_item,
    resolve_lane,
    resolve_rank_bracket,
)
from opendota_mcp.tools.annotations import READ_ONLY
from opendota_mcp.tools.descriptions import HERO, ITEM, LANE, RANK_BRACKET

PRIMARY_ATTRIBUTES: dict[str, PrimaryAttribute] = {
    "str": "Strength",
    "agi": "Agility",
    "int": "Intelligence",
    "all": "Universal",
}
MatchupSort = Literal["best", "worst", "most_played"]
MATCHUP_ORDER: dict[MatchupSort, Callable[[HeroMatchup], Any]] = {
    "best": lambda row: (-(row.win_rate or 0), -row.games),
    "worst": lambda row: (row.win_rate or 0, -row.games),
    "most_played": lambda row: -row.games,
}
ALL_BRACKETS = "All brackets"
ALL_PUBLIC_MATCHES = "All public matches"
ALL_ROLES = "All roles"
META_NOTE = (
    "Public numbers come from OpenDota's sample of Public matches over the last 7 days, "
    "Turbo excluded; pro numbers from recent Pro matches. A match falls in the Rank bracket "
    "of its players' average medal, so most Immortal players' games count under Divine."
)
PRO_MATCHES_NOTE = (
    "From Pro matches only (games in professional leagues), not Public matches, so it "
    "shows pro trends, which can differ from pubs."
)
SCENARIO_NOTE = (
    "From OpenDota's sample of Parsed matches, so a fraction of all games, and only those "
    "with a replay parsed."
)
LANE_PERFORMANCE_NOTE = f"{SCENARIO_NOTE} Games over 90:00 aren't counted."
ITEM_TIMINGS_NOTE = (
    f"{SCENARIO_NOTE} Purchases after 30:00 aren't counted. Win rates show how games went when "
    "the item was bought at that time, not what the timing caused: a hero that's already "
    "winning buys sooner."
)
DURATION_BUCKET_SECONDS = 300
"""OpenDota groups `/heroes/{id}/durations` into 5-minute bins."""


def register_hero_tools(mcp: FastMCP, api: OpenDotaClient, references: ReferenceStore) -> None:
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

    @mcp.tool(annotations=READ_ONLY)
    async def get_hero_meta(
        rank_bracket: Annotated[str | int | None, Field(description=RANK_BRACKET)] = None,
    ) -> HeroMetaResult:
        """The current meta: every hero's public win rate and pick count over the last 7
        days, plus picks, bans and win rate in recent Pro matches.

        Use for "what's strong right now", "most picked hero", "most banned in pro games".
        """
        bracket = _bracket(rank_bracket)
        stats = await api.get_hero_stats()
        reference = await references.current()
        heroes = [_hero_meta_row(entry, bracket, reference.hero_name(entry.id)) for entry in stats]
        if bracket is not None and not any(hero.picks for hero in heroes):
            neighbour = medal_name(bracket - 1 if bracket > 1 else bracket + 1)
            raise ToolError(
                f"OpenDota currently has no {medal_name(bracket)} games in its hero stats: a "
                "match counts in the bracket of its players' average medal. "
                f"Try {neighbour}, or leave rank_bracket out for all public matches."
            )
        heroes.sort(key=lambda hero: hero.win_rate or 0, reverse=True)
        return HeroMetaResult(
            rank_bracket=ALL_PUBLIC_MATCHES if bracket is None else medal_name(bracket),
            heroes=heroes,
            note=META_NOTE,
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_hero_matchups(
        hero: Annotated[str | int, Field(description=HERO)],
        sort: Annotated[
            MatchupSort,
            Field(
                description=(
                    '"best": opponents the hero beats most often (good against); "worst": '
                    'opponents it loses to most (bad against); "most_played": most games first.'
                )
            ),
        ] = "most_played",
        limit: Annotated[int, Field(ge=1, description="How many opponents to return.")] = 10,
        min_games: Annotated[
            int, Field(ge=1, description="Leave out opponents met fewer times than this.")
        ] = 10,
    ) -> HeroMatchupsResult:
        """How a hero fares against each other hero, from Pro matches only.

        Use for "what is Anti-Mage good against", "Pudge counters", "who beats Meepo".
        """
        reference = await references.current()
        found = resolve_hero(hero, reference)
        entries = [e for e in await api.get_hero_matchups(found.id) if e.games_played >= min_games]
        rows = [
            HeroMatchup(
                opponent=reference.hero_name(entry.hero_id),
                games=entry.games_played,
                win_rate=win_rate(entry.wins, entry.games_played),
            )
            for entry in entries
        ]
        rows.sort(key=MATCHUP_ORDER[sort])
        return HeroMatchupsResult(
            hero=found.localized_name,
            data_source="Pro matches",
            note=f"{PRO_MATCHES_NOTE} Opponents met fewer than {min_games} times are left out.",
            matchups=rows[:limit],
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_hero_item_popularity(
        hero: Annotated[str | int, Field(description=HERO)],
    ) -> HeroItemPopularityResult:
        """Which items pros buy on a hero, by game phase, from Pro matches only.

        Use for "what do pros build on Anti-Mage", "Pudge starting items", "late game items
        on Invoker".
        """
        reference = await references.current()
        found = resolve_hero(hero, reference)
        popularity = await api.get_hero_item_popularity(found.id)
        return HeroItemPopularityResult(
            hero=found.localized_name,
            data_source="Pro matches",
            note=PRO_MATCHES_NOTE,
            start_game=_purchases(popularity.start_game_items, reference),
            early_game=_purchases(popularity.early_game_items, reference),
            mid_game=_purchases(popularity.mid_game_items, reference),
            late_game=_purchases(popularity.late_game_items, reference),
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_hero_benchmarks(
        hero: Annotated[str | int, Field(description=HERO)],
        rank_bracket: Annotated[str | int | None, Field(description=RANK_BRACKET)] = None,
        role: Annotated[
            BenchmarkRole | None,
            Field(
                description=(
                    'Optional: only games where the hero was a "core" or a "support" (OpenDota '
                    "estimates this from farm). Leave out for all games."
                )
            ),
        ] = None,
    ) -> HeroBenchmarksResult:
        """What's normal on a hero: the GPM, XPM, last hits, kills, damage and so on reached
        at each percentile of its recent public games.

        Use for "is 600 GPM good on Anti-Mage", "average last hits on Pudge at Divine",
        "what does a good support Rubick's hero damage look like".
        """
        bracket = _bracket(rank_bracket)
        reference = await references.current()
        found = resolve_hero(hero, reference)
        benchmarks = await api.get_hero_benchmarks(found.id, bracket, role)
        return HeroBenchmarksResult(
            hero=found.localized_name,
            rank_bracket=ALL_BRACKETS if bracket is None else medal_name(bracket),
            role=role or ALL_ROLES,
            benchmarks=[
                HeroBenchmark(stat=stat, name=stat_name(stat), percentiles=_percentiles(points))
                for stat, points in benchmarks.result.items()
            ],
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_hero_lane_performance(
        hero: Annotated[str | int, Field(description=HERO)],
        lane: Annotated[str | int | None, Field(description=LANE)] = None,
    ) -> HeroLanePerformanceResult:
        """How a hero does in each Lane: games and win rate, overall and by game length.

        Use for "how does Pudge do as pos 4", "is Invoker better mid or off lane", "which lane
        is best for Dragon Knight".
        """
        reference = await references.current()
        found = resolve_hero(hero, reference)
        lane_filter = None if lane is None else resolve_lane(lane)
        entries = await api.get_hero_lane_roles(found.id)
        shown = list(LANE_NAMES) if lane_filter is None else [lane_filter.lane_role]
        return HeroLanePerformanceResult(
            hero=found.localized_name,
            note=LANE_PERFORMANCE_NOTE,
            lane_note=None if lane_filter is None else lane_filter.note,
            lanes=[_lane_performance(lane_role, entries) for lane_role in shown],
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_hero_item_timings(
        hero: Annotated[str | int, Field(description=HERO)],
        item: Annotated[str | int, Field(description=ITEM)],
    ) -> HeroItemTimingsResult:
        """A hero's win rate by when an item was bought, for items costing at least 1400 gold
        bought in the first 30 minutes.

        Use for "when does Battle Fury pay off on Anti-Mage", "how late is too late for BKB on
        Lina", "is a 12-minute Radiance good on Spectre".
        """
        reference = await references.current()
        found = resolve_hero(hero, reference)
        key = resolve_item(item, reference)
        entries = await api.get_hero_item_timings(found.id, key)
        if not entries:
            raise ToolError(
                f"OpenDota has no timings for {reference.item_name(key)} on "
                f"{found.localized_name}: it only tracks items costing at least 1400 gold, and "
                "this one may not be bought often enough on this hero. Try a costlier item; "
                "get_hero_item_popularity shows what's commonly bought on it."
            )
        return HeroItemTimingsResult(
            hero=found.localized_name,
            item=reference.item_name(key),
            note=ITEM_TIMINGS_NOTE,
            timings=[
                HeroItemTiming(
                    bought_by=entry.time,
                    bought_by_mmss=mmss(entry.time),
                    games=entry.games,
                    win_rate=win_rate(entry.wins, entry.games),
                )
                for entry in sorted(entries, key=lambda entry: entry.time)
            ],
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_hero_duration_performance(
        hero: Annotated[str | int, Field(description=HERO)],
    ) -> HeroDurationPerformanceResult:
        """A hero's win rate by game length, in 5-minute buckets, from Pro matches only.

        Use for "is Spectre a late-game hero", "is Anti-Mage stronger in short or long games",
        "when does Tinker fall off".
        """
        reference = await references.current()
        found = resolve_hero(hero, reference)
        entries = await api.get_hero_durations(found.id)
        return HeroDurationPerformanceResult(
            hero=found.localized_name,
            data_source="Pro matches",
            note=PRO_MATCHES_NOTE,
            durations=[
                HeroDurationBucket(
                    start=entry.duration_bin,
                    start_mmss=mmss(entry.duration_bin),
                    end=entry.duration_bin + DURATION_BUCKET_SECONDS,
                    end_mmss=mmss(entry.duration_bin + DURATION_BUCKET_SECONDS),
                    games=entry.games_played,
                    win_rate=win_rate(entry.wins, entry.games_played),
                )
                for entry in sorted(entries, key=lambda entry: entry.duration_bin)
            ],
        )


def _lane_performance(lane_role: int, entries: list[HeroLaneRoleEntry]) -> LanePerformance:
    in_lane = sorted((e for e in entries if e.lane_role == lane_role), key=lambda e: e.time)
    games = sum(entry.games for entry in in_lane)
    return LanePerformance(
        lane=LANE_NAMES[lane_role],
        games=games,
        win_rate=win_rate(sum(entry.wins for entry in in_lane), games),
        by_game_length=[
            LaneGameLength(
                up_to=entry.time,
                up_to_mmss=mmss(entry.time),
                games=entry.games,
                win_rate=win_rate(entry.wins, entry.games),
            )
            for entry in in_lane
        ],
    )


def _bracket(rank_bracket: str | int | None) -> int | None:
    return None if rank_bracket is None else resolve_rank_bracket(rank_bracket)


def _percentiles(points: list[BenchmarkPoint]) -> list[BenchmarkPercentile]:
    return [
        BenchmarkPercentile(
            percentile=round(point.percentile * 100),
            value=round(point.value, 2) if isinstance(point.value, float) else point.value,
        )
        for point in sorted(points, key=lambda point: point.percentile)
    ]


def _purchases(counts: Mapping[int, int], reference: Reference) -> list[ItemPurchases]:
    """Most bought first; ties alphabetical."""
    rows = [
        ItemPurchases(item=reference.item_name_by_id(item_id), purchases=count)
        for item_id, count in counts.items()
    ]
    return sorted(rows, key=lambda row: (-row.purchases, row.item))


def _hero_meta_row(entry: HeroStatsEntry, bracket: int | None, name: str) -> HeroMeta:
    """The hero's public numbers in one Rank bracket (`None`: all), and its pro numbers."""
    if bracket is None:
        picks, wins = entry.pub_pick, entry.pub_win
    else:
        picks, wins = entry.brackets[bracket].games, entry.brackets[bracket].win
    return HeroMeta(
        hero=name,
        picks=picks,
        win_rate=win_rate(wins, picks),
        pro_picks=entry.pro_pick,
        pro_bans=entry.pro_ban,
        pro_win_rate=win_rate(entry.pro_win, entry.pro_pick),
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
