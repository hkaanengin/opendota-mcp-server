"""
Tools module - registers all MCP tools
"""
from fastmcp import FastMCP # type: ignore
from .lookup_tools import register_lookup_tools
from .player_tools import register_player_tools
from .hero_tools import register_hero_tools
from .match_tools import register_match_tools
from .misc_tools import register_misc_tools


def register_all_tools(mcp: FastMCP):
    """Register all tools with the MCP server"""
    register_lookup_tools(mcp)
    register_player_tools(mcp)
    register_hero_tools(mcp)
    register_match_tools(mcp)
    register_misc_tools(mcp)