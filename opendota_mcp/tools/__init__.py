"""
Tools module - registers all MCP tools
"""
from fastmcp import FastMCP
from .lookup_tools import register_lookup_tools
from .player_tools import register_player_tools
from .hero_tools import register_hero_tools
from .match_tools import register_match_tools
from .misc_tools import register_misc_tools


def register_all_tools(mcp: FastMCP):
    """Register all tools with the MCP server"""
    import logging
    logger = logging.getLogger("opendota-server")
    
    register_lookup_tools(mcp)
    register_player_tools(mcp)
    register_hero_tools(mcp)
    register_match_tools(mcp)
    register_misc_tools(mcp)
    
    # Optional: Log count after registration
    try:
        if hasattr(mcp, '_mcp_server') and hasattr(mcp._mcp_server, 'list_tools'):
            tool_list = mcp._mcp_server.list_tools()
            if hasattr(tool_list, 'tools'):
                logger.info(f"Total tools registered: {len(tool_list.tools)}")
    except Exception as e:
        logger.warning(f"Could not verify tool count: {e}")