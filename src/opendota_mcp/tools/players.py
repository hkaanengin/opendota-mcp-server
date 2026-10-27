import asyncio
from collections.abc import Mapping, Sequence
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from opendota_mcp.api import OpenDotaClient, PlayerNotFoundError
from opendota_mcp.api.types import (
    PLAYER_STAT_FIELDS,
    HistogramEntry,
    PlayerHeroEntry,
    PlayerPeerEntry,
    PlayerResponse,
    PlayerTotalEntry,
    SearchResult,
)
from opendota_mcp.clock import Clock
from opendota_mcp.models import (
    FindPlayerResult,
    HistogramBucket,
    PlayerCandidate,
    PlayerHero,
    PlayerHeroesResult,
    PlayerHistogramResult,
    PlayerPeer,
    PlayerPeersResult,
    PlayerProfileResult,
    PlayerTotal,
    PlayerTotalsResult,
    PlayerWinLossResult,
    ResolvedPlayer,
)
from opendota_mcp.models.formatting import mmss, stat_name, utc_date, win_rate
from opendota_mcp.reference import Reference, ReferenceStore
from opendota_mcp.resolve import (
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
