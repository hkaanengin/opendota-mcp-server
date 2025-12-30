"""
Lookup tools for converting natural language to IDs
"""
from typing import Dict, Any, List
import logging
from fastmcp import FastMCP
from ..client import fetch_api
from ..config import REFERENCE_DATA
from ..resolvers import get_hero_by_id_logic, get_hero_id_by_name_logic, convert_lane_name_to_id_logic

logger = logging.getLogger("opendota-server")


def register_lookup_tools(mcp: FastMCP):
    """Register all lookup tools with the MCP server"""
    
    @mcp.tool()
    async def get_hero_id_by_name(hero_name: str) -> Dict[str, Any]:
        """
        Find a hero's ID by name with fuzzy matching for typos and case variations.
        Use this when you need to convert hero names to IDs.
        
        Args:
            hero_name: The hero name (handles typos, case variations, spaces)
        
        Returns:
            Dictionary with hero_id and hero name, or suggestions if not found
        
        Examples:
            - "Rubick", "rubick", "RUBICK", "rubik" all return Rubick's ID
            - "Anti-Mage", "anti mage", "antimage" all work
            - "rbick" returns Rubick with fuzzy matching
        """
        return await get_hero_id_by_name_logic(hero_name)
    
    @mcp.tool()
    async def convert_lane_name_to_id(lane_name: str) -> Dict[str, Any]:
        """
        Convert lane/position names to lane_role IDs.
        Use this when you need to convert natural language lanes to IDs.
        
        Args:
            lane_name: Lane name like "mid", "safe lane", "offlane", "jungle", "carry", "pos 1", etc.
        
        Returns:
            Dictionary with lane_role ID and description
        
        Examples:
            - "mid", "midlane", "pos 2" all return lane_role 2
            - "carry", "safe lane", "pos 1" all return lane_role 1
            - "offlane", "offline", "pos 3" all return lane_role 3
        """
        return convert_lane_name_to_id_logic(lane_name)
    
    @mcp.tool()
    async def search_heroes(query: str) -> List[Dict[str, Any]]:
        """
        Search for heroes by name or partial name. Returns multiple matching heroes.
        Use this for general hero searches or when uncertain about exact hero name.
        
        Args:
            query: Hero name or partial name to search for
        
        Returns:
            List of matching heroes with their IDs, names, and roles
        
        Example:
            - "mag" returns Magnus, Anti-Mage, etc.
            - "support" returns heroes with support role
        """
        query_lower = query.lower()
        
        # Use local reference data if available, otherwise fetch from API
        if REFERENCE_DATA.get('heroes'):
            heroes = [hero for hero in REFERENCE_DATA['heroes'].values()]
            logger.info(f"Using local reference data for search")
        else:
            heroes = await fetch_api("/heroes")
            logger.info("Using API data for search")
        
        matches = []
        for hero in heroes:
            # Match by name
            if query_lower in hero['localized_name'].lower():
                matches.append({
                    "hero_id": hero['id'],
                    "name": hero['localized_name'],
                    "primary_attr": hero.get('primary_attr'),
                    "roles": hero.get('roles', [])
                })
            # Match by role
            elif any(query_lower in role.lower() for role in hero.get('roles', [])):
                matches.append({
                    "hero_id": hero['id'],
                    "name": hero['localized_name'],
                    "primary_attr": hero.get('primary_attr'),
                    "roles": hero.get('roles', [])
                })
        
        return matches[:10]
    
    @mcp.tool()
    async def get_hero_by_id(hero_id: int) -> Dict[str, Any]:
        """
        Get detailed hero information by hero ID.
        Returns complete hero data including stats, attributes, and roles.
        
        Args:
            hero_id: The hero's ID (e.g., 1 for Anti-Mage)
        
        Returns:
            Dictionary with complete hero information including:
            - Basic info (name, localized_name, roles)
            - Attributes (str, agi, int and their gains)
            - Stats (health, mana, armor, attack, movement)
            - Combat info (attack range, attack rate, vision)
        
        Example:
            get_hero_by_id(1) returns all data for Anti-Mage
        """
        return await get_hero_by_id_logic(hero_id)