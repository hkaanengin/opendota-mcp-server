"""The shared player `filters`: one input model for every player stat tool, and its
translation into OpenDota query parameters plus a disclosure of what was counted."""

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any

from fastmcp.exceptions import ToolError
from pydantic import BaseModel, BeforeValidator, Field

from opendota_mcp.api import OpenDotaClient
from opendota_mcp.api.client import Params
from opendota_mcp.models import FilterDisclosure, ResolvedPlayer
from opendota_mcp.reference import Reference
from opendota_mcp.resolve.dates import resolve_date_window
from opendota_mcp.resolve.game_modes import RANKED, GameMode, resolve_game_mode
from opendota_mcp.resolve.heroes import resolve_hero
from opendota_mcp.resolve.lanes import resolve_lane
from opendota_mcp.resolve.patches import resolve_patch
from opendota_mcp.resolve.players import resolve_player

NON_STANDARD_LEFT_OUT = (
    "Turbo, other non-standard modes and games shorter than 6 minutes are left out"
)
PARSED_ONLY_NOTE = (
    "Lane is only known for parsed matches, so unparsed games are left out of these numbers."
)


def _as_list(value: Any) -> Any:
    """Let a single hero or player stand in for a list of one."""
    return [value] if isinstance(value, str | int) else value


OneOrMany = Annotated[list[str | int], BeforeValidator(_as_list)]


class PlayerFilters(BaseModel):
    """Narrows a player stat question. Every field is optional and they all combine."""

    limit: int | None = Field(None, ge=1, description="Only the latest N matches.")
    offset: int | None = Field(None, ge=0, description="Skip the latest N matches first.")
    days: str | int | None = Field(
        None,
        description='Date window: a number of days, "last 30 days", "past 2 weeks", "today", '
        '"this week", "this month" or "this year".',
    )
    patch: str | float | None = Field(
        None, description='Game patch: a version ("7.39") or "this patch" / "previous patch".'
    )
    game_mode: str | None = Field(
        None,
        description='"ranked", "unranked", "all pick", "turbo", "captains mode", "ability draft", '
        "etc. Turbo is left out unless asked for here.",
    )
    ranked_only: bool = Field(False, description="Only ranked matchmaking games.")
    lane: str | int | None = Field(
        None,
        description='A lane ("safe lane", "mid", "off lane", "jungle") or a position ("pos 1" '
        'to "pos 5", "carry", "soft support"; a bare number is a position). Positions map to '
        "their lane, and lanes are only known for parsed matches.",
    )
    hero: str | int | None = Field(
        None, description="Only games on this hero: a name, nickname or hero ID."
    )
    included_players: OneOrMany = Field(
        default_factory=list,
        description="Players who were in the match too (either team): names or account IDs.",
    )
    excluded_players: OneOrMany = Field(
        default_factory=list,
        description="Players who were not in the match: names or account IDs.",
    )
    with_heroes: OneOrMany = Field(
        default_factory=list, description='Heroes on the player\'s team, e.g. ["CM"].'
    )
    against_heroes: OneOrMany = Field(
        default_factory=list, description='Heroes on the enemy team, e.g. ["PA"].'
    )


@dataclass(frozen=True)
class ResolvedFilters:
    params: Params
    disclosure: FilterDisclosure


async def resolve_filters(
    filters: PlayerFilters | None,
    *,
    api: OpenDotaClient,
    aliases: Mapping[str, int],
    reference: Reference,
    now: float,
) -> ResolvedFilters:
    """Raises a `ToolError` naming the valid options for the first filter that can't resolve."""
    filters = filters or PlayerFilters()
    params: dict[str, int | tuple[int, ...]] = {}
    applied: list[str] = []

    if filters.limit is not None:
        params["limit"] = filters.limit
        applied.append(f"latest {filters.limit} matches")
    if filters.offset:
        params["offset"] = filters.offset
        applied.append(f"skipping the latest {filters.offset}")
    if filters.days is not None:
        window = resolve_date_window(filters.days, now)
        params["date"] = window.days
        applied.append(window.label)
    if filters.patch is not None:
        patch = resolve_patch(filters.patch, reference.patches)
        params["patch"] = patch.id
        applied.append(f"patch {patch.name}")

    modes = _game_modes(filters)
    for mode in modes:
        if mode.lobby_type is not None:
            params["lobby_type"] = mode.lobby_type
        if mode.game_mode is not None:
            params["game_mode"] = mode.game_mode
        if not mode.standard:
            params["significant"] = 0
        applied.append(mode.label)

    lane_note = parsed_only_note = None
    if filters.lane is not None:
        lane = resolve_lane(filters.lane)
        params["lane_role"] = lane.lane_role
        applied.append(lane.label)
        lane_note, parsed_only_note = lane.note, PARSED_ONLY_NOTE

    if filters.hero is not None:
        hero = resolve_hero(filters.hero, reference)
        params["hero_id"] = hero.id
        applied.append(f"playing {hero.localized_name}")
    for key, heroes, phrase in (
        ("with_hero_id", filters.with_heroes, "with {} on their team"),
        ("against_hero_id", filters.against_heroes, "against {}"),
    ):
        if heroes:
            resolved = {hero.id: hero for hero in (resolve_hero(h, reference) for h in heroes)}
            params[key] = tuple(sorted(resolved))
            applied.append(phrase.format(_and(sorted(h.localized_name for h in resolved.values()))))

    for key, players, phrase in (
        ("included_account_id", filters.included_players, "with {} in the match"),
        ("excluded_account_id", filters.excluded_players, "without {} in the match"),
    ):
        if players:
            found = await _resolve_players(players, api, aliases)
            params[key] = tuple(sorted(found))
            applied.append(phrase.format(_and([_player(p) for p in found.values()])))

    return ResolvedFilters(
        params=params,
        disclosure=FilterDisclosure(
            applied=applied,
            game_modes=_game_modes_counted(modes),
            lane_note=lane_note,
            parsed_only_note=parsed_only_note,
        ),
    )


def _game_modes(filters: PlayerFilters) -> list[GameMode]:
    """Ranked first, then the asked-for mode, so the disclosure reads "Ranked All Pick"."""
    modes = list(resolve_game_mode(filters.game_mode)) if filters.game_mode is not None else []
    if not filters.ranked_only or RANKED in modes:
        return modes
    if any(mode.lobby_type is not None for mode in modes):
        raise ToolError(
            f"ranked_only can't be combined with game_mode {filters.game_mode!r}. Drop one of them."
        )
    return [RANKED, *modes]


def _game_modes_counted(modes: Sequence[GameMode]) -> str:
    if not modes:
        return (
            f"Standard games only: {NON_STANDARD_LEFT_OUT}. "
            'Set game_mode to "turbo" to count Turbo.'
        )
    counted = f"{' '.join(mode.label for mode in modes)} games only."
    if all(mode.standard for mode in modes):
        counted += f" {NON_STANDARD_LEFT_OUT}."
    return counted


async def _resolve_players(
    players: Sequence[str | int], api: OpenDotaClient, aliases: Mapping[str, int]
) -> dict[int, ResolvedPlayer]:
    resolved = await asyncio.gather(*(resolve_player(p, api, aliases) for p in players))
    return {player.account_id: player for player in resolved}


def _player(player: ResolvedPlayer) -> str:
    return (
        f"{player.persona_name} ({player.account_id})"
        if player.persona_name
        else str(player.account_id)
    )


def _and(names: Sequence[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
