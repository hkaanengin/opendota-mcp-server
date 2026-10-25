"""An Account ID, a Player alias or a Persona name → the Player it identifies.

A Persona name is never unique, so a name is only used when OpenDota knows exactly one
Player by it; anything else fails with candidates rather than guessing.
"""

from collections.abc import Mapping

from fastmcp.exceptions import ToolError

from opendota_mcp.api import OpenDotaClient, PlayerNotFoundError
from opendota_mcp.api.types import SearchResult
from opendota_mcp.models import ResolvedPlayer

MAX_CANDIDATES = 5


async def resolve_player(
    text: str | int, api: OpenDotaClient, aliases: Mapping[str, int]
) -> ResolvedPlayer:
    """By Account ID, then configured Player alias (case-insensitive), then exact-name search."""
    wanted = str(text).strip()
    account_id = (
        int(wanted) if wanted.isascii() and wanted.isdigit() else aliases.get(wanted.lower())
    )
    if account_id is not None:
        try:
            player = await api.get_player(account_id)
        except PlayerNotFoundError:
            raise ToolError(
                f"No player with account ID {account_id} on OpenDota. Check the number: it's "
                "the Friend ID in the Dota client, or search by name with find_player."
            ) from None
        return ResolvedPlayer(account_id=account_id, persona_name=player.profile.personaname)

    found = await api.search_players(wanted)
    exact = [entry for entry in found if same_name(entry.personaname, wanted)]
    if len(exact) == 1:
        return ResolvedPlayer(account_id=exact[0].account_id, persona_name=exact[0].personaname)
    if exact:
        raise ToolError(
            f"Several players are named {wanted!r}: {_candidates(exact)}. "
            "Ask which one is meant (find_player shows more detail), then call again with "
            "their account ID."
        )
    if found:
        raise ToolError(
            f"No player is named exactly {wanted!r}. Closest: {_candidates(found)}. "
            "Ask which one is meant, then call again with their account ID."
        )
    raise ToolError(
        f"No player named {wanted!r} on OpenDota. Ask for their account ID (the Friend ID "
        "in the Dota client); names need at least 3 characters to be searched."
    )


def same_name(persona_name: str | None, wanted: str) -> bool:
    """Exact apart from case and surrounding spaces, so "ammar" finds a lone "Ammar"."""
    return persona_name is not None and persona_name.strip().casefold() == wanted.casefold()


def _candidates(found: list[SearchResult]) -> str:
    shown = [
        f"{entry.personaname} (account ID {entry.account_id}"
        + (f", last played {entry.last_match_time.date()}" if entry.last_match_time else "")
        + ")"
        for entry in found[:MAX_CANDIDATES]
    ]
    more = len(found) - MAX_CANDIDATES
    return "; ".join(shown) + (f"; and {more} more" if more > 0 else "")
