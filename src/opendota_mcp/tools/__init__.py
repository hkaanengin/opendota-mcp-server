"""MCP tools, one module per area. Each tool is thin: resolve → fetch → shape."""

from collections.abc import Mapping

from fastmcp import FastMCP

from opendota_mcp.api import OpenDotaClient
from opendota_mcp.clock import Clock
from opendota_mcp.reference import ReferenceStore
from opendota_mcp.tools.heroes import register_hero_tools
from opendota_mcp.tools.items import register_item_tools
from opendota_mcp.tools.matches import register_match_tools
from opendota_mcp.tools.players import register_player_tools
from opendota_mcp.tools.records import register_records_tools


def register_all_tools(
    mcp: FastMCP,
    api: OpenDotaClient,
    references: ReferenceStore,
    player_aliases: Mapping[str, int],
    clock: Clock,
) -> None:
    register_hero_tools(mcp, references)
    register_item_tools(mcp, references)
    register_match_tools(mcp, api, references)
    register_player_tools(mcp, api, references, player_aliases, clock)
    register_records_tools(mcp, api, references)
