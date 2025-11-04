"""
Match-related tools
"""
import logging
from fastmcp import FastMCP
from ..client import fetch_api, get_http_client, rate_limiter
from ..config import OPENDOTA_BASE_URL
from ..utils import get_account_id
from typing import List, Dict, Any

logger = logging.getLogger("opendota-server")


def register_match_tools(mcp: FastMCP):
    """Register all match-related tools with the MCP server"""
    
    @mcp.tool()
    async def get_recent_matches(player_name: str) -> List[Dict[str, Any]]:
        """
        Get player's recent matches.
        
        Args:
            player_name: The Dota 2 player name to search for
        
        Returns:
            List of recent match objects with details like match_id, hero_id, kills, deaths, assists, etc.
        """
        try:
            account_id = await get_account_id(player_name)
            return await fetch_api(f"/players/{account_id}/recentMatches")
        except Exception as e:
            logger.error(f"Error getting recent matches for '{player_name}': {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def request_parse_match(match_id: int) -> dict:
        """
        Submit a new parse request for a specific match
        
        Args:
            match_id: Match ID
        
        Returns:
            Dictionary with parse request status
        """
        client = await get_http_client()
        await rate_limiter.acquire()
        
        response = await client.post(f"{OPENDOTA_BASE_URL}/request/{match_id}")
        response.raise_for_status()
        return response.json()

    @mcp.tool()
    async def get_match_details(match_id: int) -> Dict[str, Any]:
        """
        Get details for a specific match, used for analysing match data in detail.
        
        Args:
            match_id: Match ID
        
        Returns:
            Detailed match information including all players, items, abilities, etc.
        """
        return await fetch_api(f"/matches/{match_id}")