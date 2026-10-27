import asyncio
from collections.abc import Callable, Mapping, Sequence
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from opendota_mcp.api import OpenDotaClient, PlayerNotFoundError
from opendota_mcp.api.types import (
    PLAYER_STAT_FIELDS,
    CountEntry,
    HistogramEntry,
    PlayerHeroEntry,
    PlayerMatchEntry,
    PlayerPeerEntry,
    PlayerResponse,
    PlayerTotalEntry,
    SearchResult,
)
from opendota_mcp.clock import Clock
from opendota_mcp.models import (
    BreakdownRow,
    FindPlayerResult,
    HistogramBucket,
    PlayerBreakdownResult,
    PlayerCandidate,
    PlayerHero,
    PlayerHeroesResult,
    PlayerHistogramResult,
    PlayerMatch,
    PlayerMatchesResult,
    PlayerPeer,
    PlayerPeersResult,
    PlayerProfileResult,
    PlayerRankHistoryResult,
    PlayerTotal,
    PlayerTotalsResult,
    PlayerWinLossResult,
    RankChange,
    ResolvedPlayer,
)
from opendota_mcp.models.formatting import (
    mmss,
    stat_name,
    utc_date,
    utc_datetime,
    win_rate,
)
from opendota_mcp.models.labels import game_mode_name, lobby_type_name, region_name
from opendota_mcp.objectives import side_of_slot
from opendota_mcp.reference import Reference, ReferenceStore
from opendota_mcp.resolve import (
    LANE_NAMES,
    MAX_CANDIDATES,
    PlayerFilters,
    ResolvedFilters,
    format_rank_tier,
    resolve_filters,
    resolve_player,
    resolve_stat_field,
    same_name,
)
from opendota_mcp.tools.annotations import READ_ONLY
from opendota_mcp.tools.descriptions import FILTERS, PLAYER

TOP_HEROES = 10
DEFAULT_MATCHES = 20
UNPARSED_LANE = "unknown (match not parsed)"
MIN_GAMES = (
    "Leave out rows with fewer games than this (default 1). Applied after the filters, "
    "e.g. 10 to skip one-off games."
)
PROFILE_URL = "https://www.opendota.com/players/{account_id}"


def register_player_tools(
    mcp: FastMCP,
    api: OpenDotaClient,
    references: ReferenceStore,
    player_aliases: Mapping[str, int],
    clock: Clock,
) -> None:
    async def resolve_request(
        player: str | int, filters: PlayerFilters | None
    ) -> tuple[ResolvedPlayer, ResolvedFilters, Reference]:
        """The Player and filters a filtered tool answers for, resolved together."""
        reference = await references.current()
        resolved, applied = await asyncio.gather(
            resolve_player(player, api, player_aliases),
            resolve_filters(
                filters, api=api, aliases=player_aliases, reference=reference, now=clock.time()
            ),
        )
        return resolved, applied, reference

    @mcp.tool(annotations=READ_ONLY)
    async def find_player(
        name: Annotated[
            str, Field(description="The Persona name (Steam display name) to look up.")
        ],
    ) -> FindPlayerResult:
        """Players OpenDota knows by a name, with what tells them apart: avatar, latest match,
        rank and profile link. Names aren't unique, so use this to confirm who someone is
        and get their account ID before asking about their stats.

        Use for "find my account", "which one is me", or after a name came back ambiguous.
        """
        wanted = name.strip()
        found = await api.search_players(wanted)
        top = found[:MAX_CANDIDATES]
        players = await asyncio.gather(
            *(api.get_player(entry.account_id) for entry in top), return_exceptions=True
        )
        candidates = []
        for entry, player in zip(top, players, strict=True):
            # A search row can outlive its profile; skip it rather than fail the whole search.
            if isinstance(player, PlayerNotFoundError):
                continue
            if isinstance(player, BaseException):
                raise player
            candidates.append(_candidate(entry, wanted, player))
        return FindPlayerResult(players_found=len(found), candidates=candidates)

    @mcp.tool(annotations=READ_ONLY)
    async def get_player_profile(
        player: Annotated[str | int, Field(description=PLAYER)],
    ) -> PlayerProfileResult:
        """A Player's overview: current rank, overall wins and losses, and most-played heroes.

        Use for "what rank am I", "how am I doing overall", "what are my main heroes".
        """
        resolved = await resolve_player(player, api, player_aliases)
        profile, win_loss, heroes = await asyncio.gather(
            api.get_player(resolved.account_id),
            api.get_player_win_loss(resolved.account_id),
            api.get_player_heroes(resolved.account_id),
        )
        reference = await references.current()
        return PlayerProfileResult(
            resolved_player=resolved,
            rank=_rank(profile),
            wins=win_loss.win,
            losses=win_loss.lose,
            win_rate=win_rate(win_loss.win, win_loss.win + win_loss.lose),
            top_heroes=_heroes(heroes, reference)[:TOP_HEROES],
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_player_win_loss(
        player: Annotated[str | int, Field(description=PLAYER)],
        filters: Annotated[PlayerFilters | None, Field(description=FILTERS)] = None,
    ) -> PlayerWinLossResult:
        """A Player's wins, losses and win rate, optionally narrowed by `filters`.

        Use for "what's my win rate on Pudge this patch", "how do I do in ranked as pos 1",
        "my record with a friend in the last 30 days".
        """
        resolved, applied, _ = await resolve_request(player, filters)
        win_loss = await api.get_player_win_loss(resolved.account_id, applied.params)
        return PlayerWinLossResult(
            resolved_player=resolved,
            wins=win_loss.win,
            losses=win_loss.lose,
            win_rate=win_rate(win_loss.win, win_loss.win + win_loss.lose),
            filters=applied.disclosure,
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_player_heroes(
        player: Annotated[str | int, Field(description=PLAYER)],
        filters: Annotated[PlayerFilters | None, Field(description=FILTERS)] = None,
        min_games: Annotated[int, Field(ge=1, description=MIN_GAMES)] = 1,
    ) -> PlayerHeroesResult:
        """The heroes a Player plays, with games, wins and win rate on each, most-played first.

        Use for "what heroes do I play most", "my best heroes this patch", "my win rate on each
        carry I play".
        """
        resolved, applied, reference = await resolve_request(player, filters)
        heroes = await api.get_player_heroes(resolved.account_id, applied.params)
        return PlayerHeroesResult(
            resolved_player=resolved,
            heroes=_heroes([e for e in heroes if e.games >= min_games], reference),
            filters=applied.disclosure,
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_player_peers(
        player: Annotated[str | int, Field(description=PLAYER)],
        filters: Annotated[PlayerFilters | None, Field(description=FILTERS)] = None,
        min_games: Annotated[int, Field(ge=1, description=MIN_GAMES)] = 1,
    ) -> PlayerPeersResult:
        """Who a Player plays with on their team, and how often they win together, most games
        first. Only games on the same team count; players met only as opponents are left out.
        Each peer comes with their account ID for follow-up questions.

        Use for "who do I play with most", "my win rate with my friends", "best duo partner".
        """
        resolved, applied, _ = await resolve_request(player, filters)
        peers = await api.get_player_peers(resolved.account_id, applied.params)
        together = sorted(
            (peer for peer in peers if peer.with_games >= min_games),
            key=lambda peer: -peer.with_games,
        )
        return PlayerPeersResult(
            resolved_player=resolved,
            peers=[_peer(peer) for peer in together],
            filters=applied.disclosure,
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_player_totals(
        player: Annotated[str | int, Field(description=PLAYER)],
        filters: Annotated[PlayerFilters | None, Field(description=FILTERS)] = None,
    ) -> PlayerTotalsResult:
        """A Player's lifetime totals and per-game averages for every stat: kills, deaths, last
        hits, gold and XP per minute, hero damage, wards bought, time played and more.

        Use for "how many kills have I ever got", "my average GPM", "my average game length".
        """
        resolved, applied, _ = await resolve_request(player, filters)
        totals = await api.get_player_totals(resolved.account_id, applied.params)
        return PlayerTotalsResult(
            resolved_player=resolved,
            totals=[_total(total) for total in totals],
            filters=applied.disclosure,
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_player_histogram(
        player: Annotated[str | int, Field(description=PLAYER)],
        field: Annotated[
            str,
            Field(
                description=(
                    "The stat, in everyday words or OpenDota's name: kills, deaths, assists, "
                    "kda, gpm, xpm, last hits, denies, lane efficiency, duration, level, hero "
                    "damage, tower damage, hero healing, stuns, tower kills, neutral kills, "
                    "courier kills, tps, observer wards, sentry wards, gems, rapiers, pings, "
                    "throw, comeback, stomp, loss, apm."
                )
            ),
        ],
        filters: Annotated[PlayerFilters | None, Field(description=FILTERS)] = None,
    ) -> PlayerHistogramResult:
        """How one stat is spread across a Player's games: games and win rate in each range,
        low to high.

        Use for "how is my GPM distributed", "how often do I die more than 10 times", "do I
        win more in long games".
        """
        stat = resolve_stat_field(field, PLAYER_STAT_FIELDS)
        resolved, applied, _ = await resolve_request(player, filters)
        buckets = await api.get_player_histogram(resolved.account_id, stat, applied.params)
        return PlayerHistogramResult(
            resolved_player=resolved,
            field=stat,
            stat=stat_name(stat),
            games=sum(bucket.games for bucket in buckets),
            buckets=_buckets(buckets, duration=stat == "duration"),
            filters=applied.disclosure,
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_player_breakdown(
        player: Annotated[str | int, Field(description=PLAYER)],
        filters: Annotated[PlayerFilters | None, Field(description=FILTERS)] = None,
    ) -> PlayerBreakdownResult:
        """A Player's games, wins and win rate split by game mode, lobby type (ranked or not),
        lane, patch and server region, all in one call.

        Use for "do I do better in mid or safe lane", "my ranked vs unranked win rate", "how
        did I do each patch", "which region do I play on".
        """
        resolved, applied, reference = await resolve_request(player, filters)
        counts = await api.get_player_counts(resolved.account_id, applied.params)
        # Known lanes in order, then unparsed games (lane_role 0) last.
        lanes = [
            _row(_lane_name(lane), entry)
            for lane, entry in sorted(counts.lane_role.items(), key=lambda item: item[0] == 0)
        ]
        return PlayerBreakdownResult(
            resolved_player=resolved,
            game_modes=_rows(counts.game_mode, game_mode_name),
            lobby_types=_rows(counts.lobby_type, lobby_type_name),
            lanes=lanes,
            patches=[
                _row(reference.patch_name(patch), entry)
                for patch, entry in sorted(counts.patch.items(), reverse=True)
            ],
            regions=_rows(counts.region, region_name),
            filters=applied.disclosure,
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_player_matches(
        player: Annotated[str | int, Field(description=PLAYER)],
        filters: Annotated[PlayerFilters | None, Field(description=FILTERS)] = None,
    ) -> PlayerMatchesResult:
        """A Player's matches, newest first: hero, result, KDA, GPM, XPM, length and start
        time. The latest 20 unless `filters.limit` asks for more; page further back with
        `filters.offset` (the response gives the next one).

        Use for "my last 10 games", "my last 50 ranked Pudge games", "games I played with my
        friend this week". Pass a match ID to get_match for its details.
        """
        resolved, applied, reference = await resolve_request(player, filters)
        limit = filters.limit if filters and filters.limit else DEFAULT_MATCHES
        offset = filters.offset if filters and filters.offset else 0
        matches = await api.get_player_matches(
            resolved.account_id, {**applied.params, "limit": limit}
        )
        return PlayerMatchesResult(
            resolved_player=resolved,
            matches=[_match(match, reference) for match in matches],
            next_offset=offset + limit if len(matches) >= limit else None,
            filters=applied.disclosure,
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_player_rank_history(
        player: Annotated[str | int, Field(description=PLAYER)],
    ) -> PlayerRankHistoryResult:
        """How a Player's rank (medal) has changed over time, oldest first, with their current
        rank. OpenDota only records changes it saw, so the history can be short or empty.

        Use for "when did I reach Divine", "how has my rank changed", "did I drop a medal".
        """
        resolved = await resolve_player(player, api, player_aliases)
        profile, ratings = await asyncio.gather(
            api.get_player(resolved.account_id), api.get_player_ratings(resolved.account_id)
        )
        return PlayerRankHistoryResult(
            resolved_player=resolved,
            current_rank=_rank(profile),
            changes=[
                RankChange(time=rating.time, rank=format_rank_tier(rating.rank_tier))
                for rating in sorted(ratings, key=lambda rating: rating.time)
            ],
        )


def _lane_name(lane_role: int) -> str:
    if lane_role == 0:
        return UNPARSED_LANE
    return LANE_NAMES.get(lane_role) or f"Unknown lane (id {lane_role})"


def _row(label: str, entry: CountEntry) -> BreakdownRow:
    return BreakdownRow(
        label=label, games=entry.games, wins=entry.win, win_rate=win_rate(entry.win, entry.games)
    )


def _rows(counts: Mapping[int, CountEntry], name: Callable[[int], str]) -> list[BreakdownRow]:
    """Labelled rows, most games first."""
    return [
        _row(name(key), entry)
        for key, entry in sorted(counts.items(), key=lambda item: -item[1].games)
    ]


def _match(match: PlayerMatchEntry, reference: Reference) -> PlayerMatch:
    result = None
    if match.radiant_win is not None:
        radiant = side_of_slot(match.player_slot) == "Radiant"
        result = "win" if radiant == match.radiant_win else "loss"
    return PlayerMatch(
        match_id=match.match_id,
        hero=reference.hero_name(match.hero_id),
        result=result,
        kills=match.kills,
        deaths=match.deaths,
        assists=match.assists,
        gold_per_min=match.gold_per_min,
        xp_per_min=match.xp_per_min,
        duration=match.duration,
        duration_mmss=mmss(match.duration),
        start_time=utc_datetime(match.start_time),
        game_mode=game_mode_name(match.game_mode),
        lobby_type=lobby_type_name(match.lobby_type),
    )


def _heroes(heroes: Sequence[PlayerHeroEntry], reference: Reference) -> list[PlayerHero]:
    return [
        PlayerHero(
            hero=reference.hero_name(entry.hero_id),
            games=entry.games,
            wins=entry.win,
            win_rate=win_rate(entry.win, entry.games),
        )
        for entry in sorted(heroes, key=lambda entry: -entry.games)
    ]


def _peer(peer: PlayerPeerEntry) -> PlayerPeer:
    return PlayerPeer(
        persona_name=peer.personaname,
        account_id=peer.account_id,
        games=peer.with_games,
        wins=peer.with_win,
        win_rate=win_rate(peer.with_win, peer.with_games),
        last_played_date=utc_date(peer.last_played) if peer.last_played else None,
    )


def _total(total: PlayerTotalEntry) -> PlayerTotal:
    average = total.sum / total.n if total.n else None
    return PlayerTotal(
        field=total.field,
        stat=stat_name(total.field),
        games=total.n,
        total=total.sum,
        average=round(average, 2) if average is not None else None,
        average_mmss=mmss(average) if average is not None and total.field == "duration" else None,
    )


def _buckets(buckets: Sequence[HistogramEntry], *, duration: bool) -> list[HistogramBucket]:
    """Buckets with their ranges, trimmed of the empty ones at either end."""
    played = [i for i, bucket in enumerate(buckets) if bucket.games]
    if not played:
        return []
    width = buckets[1].x - buckets[0].x if len(buckets) > 1 else 0
    shaped = []
    for i in range(played[0], played[-1] + 1):
        bucket = buckets[i]
        high = buckets[i + 1].x if i + 1 < len(buckets) else bucket.x + width
        shaped.append(
            HistogramBucket(
                low=bucket.x,
                high=high,
                games=bucket.games,
                wins=bucket.win,
                win_rate=win_rate(bucket.win, bucket.games),
                range_mmss=f"{mmss(bucket.x)}-{mmss(high)}" if duration else None,
            )
        )
    return shaped


def _rank(player: PlayerResponse) -> str:
    return format_rank_tier(player.rank_tier, player.leaderboard_rank)


def _candidate(entry: SearchResult, wanted: str, player: PlayerResponse) -> PlayerCandidate:
    return PlayerCandidate(
        persona_name=entry.personaname,
        account_id=entry.account_id,
        exact_name_match=same_name(entry.personaname, wanted),
        avatar=entry.avatarfull,
        last_match_date=entry.last_match_time.date() if entry.last_match_time else None,
        rank=_rank(player),
        profile_url=PROFILE_URL.format(account_id=entry.account_id),
    )
