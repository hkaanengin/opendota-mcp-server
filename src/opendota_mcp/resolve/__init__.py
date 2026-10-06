"""Natural language → canonical OpenDota values. Failures raise `ToolError`s with suggestions."""

from opendota_mcp.resolve.stat_fields import resolve_stat_field

__all__ = ["resolve_stat_field"]
