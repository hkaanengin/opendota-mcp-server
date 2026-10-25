"""Natural language → canonical OpenDota values. Failures raise `ToolError`s with suggestions."""

from opendota_mcp.resolve.heroes import resolve_hero
from opendota_mcp.resolve.items import resolve_item
from opendota_mcp.resolve.stat_fields import resolve_stat_field

__all__ = ["resolve_hero", "resolve_item", "resolve_stat_field"]
