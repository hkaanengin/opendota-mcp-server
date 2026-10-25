import asyncio
from collections.abc import Mapping
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from opendota_mcp.api import OpenDotaClient, PlayerNotFoundError
from opendota_mcp.api.types import PlayerResponse, SearchResult
from opendota_mcp.models import FindPlayerResult, PlayerCandidate, PlayerHero, PlayerProfileResult
from opendota_mcp.models.formatting import win_rate
from opendota_mcp.reference import ReferenceStore
from opendota_mcp.resolve import MAX_CANDIDATES, format_rank_tier, resolve_player, same_name
from opendota_mcp.tools.annotations import READ_ONLY
from opendota_mcp.tools.descriptions import PLAYER

TOP_HEROES = 10
PROFILE_URL = "https://www.opendota.com/players/{account_id}"


def register_player_tools(
    mcp: FastMCP,
    api: OpenDotaClient,
    references: ReferenceStore,
    player_aliases: Mapping[str, int],
) -> None:
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
            top_heroes=[
                PlayerHero(
                    hero=reference.hero_name(entry.hero_id),
                    games=entry.games,
                    wins=entry.win,
                    win_rate=win_rate(entry.win, entry.games),
                )
                for entry in sorted(heroes, key=lambda entry: -entry.games)[:TOP_HEROES]
            ],
        )


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
