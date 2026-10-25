"""Natural language → canonical OpenDota values. Failures raise `ToolError`s with suggestions."""

from opendota_mcp.resolve.heroes import resolve_hero
from opendota_mcp.resolve.items import resolve_item
from opendota_mcp.resolve.medals import format_rank_tier
from opendota_mcp.resolve.players import MAX_CANDIDATES, resolve_player, same_name
from opendota_mcp.resolve.stat_fields import resolve_stat_field

__all__ = [
    "MAX_CANDIDATES",
    "format_rank_tier",
    "resolve_hero",
    "resolve_item",
    "resolve_player",
    "resolve_stat_field",
    "same_name",
]
