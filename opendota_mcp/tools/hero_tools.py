"""
Hero-related tools
"""
from typing import Dict, Union, List, Any
import logging
from fastmcp import FastMCP
from ..client import fetch_api
from ..utils import simplify_response
from ..resolvers import resolve_hero, resolve_item_name

logger = logging.getLogger("opendota-server")


def register_hero_tools(mcp: FastMCP):
    """Register all hero-related tools with the MCP server"""
    
    @mcp.tool()
    async def get_heroes() -> List[Dict[str, Any]]:
        """
        Get comprehensive list of all available heroes with their attributes and basic information.
        
        Returns:
            Array of hero objects, each containing:
            - id (int): Hero ID
            - localized_name (str): Hero display name (e.g. "Anti-Mage")
            - primary_attr (str): Primary attribute (str/agi/int/all)
            - attack_type (str): Melee or Ranged
            - roles (array): Hero roles (Carry, Support, etc.)
        """
        gh_response = await fetch_api("/heroes")
        gh_data = simplify_response(gh_response, remove_keys=["name", "legs"])
        return gh_data

    @mcp.tool()
    async def get_hero_matchups(hero_id: Union[int, str]) -> List[Dict[str, Any]]:
        """
        Get results against other heroes for a specific hero (win/loss rates, counter-picks).
        
        Args:
            hero_id: Hero ID or hero name (e.g., 86 or "Rubick")
        
        Returns:
            Array of matchup objects showing how this hero performs against other heroes.
            
        Example: Use this to find which heroes counter or are countered by the specified hero.
        """
        try:
            hero_id = await resolve_hero(hero_id)
            result = await fetch_api(f"/heroes/{hero_id}/matchups")

            structured_result = [{'hero_id': resolve_hero(item['hero_id']),
                                'games': item['games_played'],
                                'win': item['win'],
                                'loss': item['games_played'] - item['win'],
                                'win_rate': (item['win']/item['games_played']) * 100
                                } for item in result]
                           
            return structured_result
        except ValueError as e:
            logger.error(f"Error resolving hero: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def get_hero_item_popularity(hero_id: Union[int, str]) -> Dict[str, Any]:
        """
        Get item popularity for a hero categorized by game phase (start, early, mid, late).
        
        Args:
            hero_id: Hero ID or hero name (e.g., 86 or "Rubick")
        
        Returns:
            Object with game phases (start_game_items, early_game_items, mid_game_items, late_game_items).
            Each phase contains items with their popularity counts and win rates.
            
        Example: Use this to understand optimal item builds and timing for a hero.
        """
        try:
            hero_id = await resolve_hero(hero_id)
            result = await fetch_api(f"/heroes/{hero_id}/itemPopularity")

            structured_result = {}
            
            for game_phase, items in result.items():
                phase_items = {}
                for item_id, count in items.items():
                    item_name = await resolve_item_name(item_id)
                    phase_items[item_name] = count
                structured_result[game_phase] = phase_items

            return structured_result
        
        except ValueError as e:
            logger.error(f"Error resolving hero: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error in get_hero_item_popularity: {e}", exc_info=True)
            return {"error": f"Unexpected error: {str(e)}"}

    @mcp.tool()
    async def get_hero_stats() -> dict:
        """
        Get aggregated statistics about hero performance in recent matches (win rates, pick rates).
        
        Returns:
            Array of hero statistics including win rates, pick rates, and performance metrics
        """
        return await fetch_api("/heroStats")