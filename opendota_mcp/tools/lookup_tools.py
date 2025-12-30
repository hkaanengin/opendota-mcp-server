"""
Lookup tools for converting natural language to IDs
"""
from typing import Dict, Any, List, Union
import logging
from fastmcp import FastMCP
from ..client import fetch_api
from ..config import REFERENCE_DATA
from ..resolvers import get_hero_by_id_logic, get_hero_id_by_name_logic, convert_lane_name_to_id_logic, resolve_hero, resolve_item_name, resolve_item_by_name, get_item_details_logic, get_aghs_details_logic

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
    async def search_hero_names(query: str) -> List[Dict[str, Any]]:
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
    async def get_hero_details(hero: Union[int, str]) -> Dict[str, Any]:
        """
        Get detailed hero information by hero name or ID with fuzzy matching.

        Use this when users ask about heroes:
        - "What are Anti-Mage's stats?"
        - "Tell me about Pudge"
        - "Show me Invoker details"

        Supports fuzzy matching for typos and variations:
        - "Anti-Mage", "antimage", "anti mage" all work
        - "Pudge", "pudge", "PUDGE" all work
        - "Shadow Fiend", "shadowfiend", "nevermore" all work

        Args:
            hero: Hero name (display name, internal name, fuzzy match) or hero ID
                  Examples: "Anti-Mage", "antimage", "pudge", 1

        Returns:
            Dictionary with complete hero information including:
            - id: Hero ID
            - name: Internal name (e.g., "npc_dota_hero_antimage")
            - localized_name: Display name (e.g., "Anti-Mage")
            - primary_attr: Primary attribute ("str", "agi", "int", "all")
            - attack_type: "Melee" or "Ranged"
            - roles: List of roles (e.g., ["Carry", "Escape", "Nuker"])
            - Base stats: base_health, base_mana, base_armor, etc.
            - Attribute gains: str_gain, agi_gain, int_gain
            - Combat stats: attack_range, attack_rate, move_speed, vision
            - All other hero statistics

        Examples:
            get_hero_details("Anti-Mage") → Full Anti-Mage data
            get_hero_details("antimage") → Same result (fuzzy match)
            get_hero_details("Pudge") → Full Pudge data
            get_hero_details(1) → Anti-Mage data (by ID)
        """
        try:
            hero_id = await resolve_hero(hero)
            return await get_hero_by_id_logic(hero_id)
        except ValueError as e:
            logger.error(f"Error resolving hero '{hero}': {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def get_item_details(item_name: str) -> Dict[str, Any]:
        """
        Get detailed item information by item name with fuzzy matching.

        Use this when users ask about items:
        - "What does Diffusal Blade do?"
        - "Show me Octarine Core"
        - "Tell me about BKB"

        Supports fuzzy matching for typos and variations:
        - "Diffusal", "diffusal blade", "Diffusal Blade" all work
        - "Octarine", "octarine core", "Octarine Core" all work
        - "bkb", "Black King Bar", "black king bar" all work

        Args:
            item_name: Item name (display name, internal name, or fuzzy match)
                      Examples: "Diffusal Blade", "diffusal", "octarine core"

        Returns:
            Dictionary with complete item information including:
            - dname: Display name (e.g., "Diffusal Blade")
            - cost: Gold cost
            - abilities: List of active/passive abilities with descriptions
            - hint: Usage hints and tips
            - stats: Attribute bonuses (damage, mana, health, etc.)
            - notes: Additional information

        Examples:
            get_item_details("Diffusal Blade") → Full Diffusal Blade data
            get_item_details("diffusal") → Same result (fuzzy match)
            get_item_details("Octarine Core") → Full Octarine Core data
            get_item_details("octarine") → Same result (fuzzy match)
        """
        try:
            internal_name = await resolve_item_by_name(item_name)

            response = await get_item_details_logic(internal_name)

            return response
        except ValueError as e:
            logger.error(f"Error resolving item '{item_name}': {e}")
            return {"error": str(e)}


    @mcp.tool()
    async def get_aghs_details(hero: Union[int, str]) -> Dict[str, Any]:
        """
        Get Aghanim's Scepter and Shard upgrade details for a hero with fuzzy matching.

        Use this when users ask about Aghanim's upgrades:
        - "What does Aghanim's Scepter do for Pudge?"
        - "Show me Anti-Mage's shard upgrade"
        - "What are Invoker's Aghs upgrades?"
        - "Does Rubick have a shard?"

        Supports fuzzy matching for hero names:
        - "Pudge", "pudge", "Anti-Mage", "antimage" all work
        - "Shadow Fiend", "shadowfiend", "sf" all work (if alias exists)

        Args:
            hero: Hero name (display name, internal name, fuzzy match) or hero ID
                  Examples: "Pudge", "antimage", "Shadow Fiend", 1

        Returns:
            Dictionary with Aghanim's upgrade information:
            - hero_id: Hero ID
            - hero_name: Internal hero name (e.g., "npc_dota_hero_pudge")
            - has_scepter: Whether the hero has a scepter upgrade (bool)
            - scepter_desc: Description of scepter upgrade (if has_scepter)
            - scepter_skill_name: Name of skill affected by scepter (if has_scepter)
            - scepter_new_skill: Whether scepter adds a new skill (bool, if has_scepter)
            - has_shard: Whether the hero has a shard upgrade (bool)
            - shard_desc: Description of shard upgrade (if has_shard)
            - shard_skill_name: Name of skill affected by shard (if has_shard)
            - shard_new_skill: Whether shard adds a new skill (bool, if has_shard)

        Examples:
            get_aghs_details("Pudge") → Full Aghanim's info for Pudge
            get_aghs_details("Anti-Mage") → Scepter and Shard details for Anti-Mage
            get_aghs_details(1) → Aghanim's details by hero ID
        """
        try:
            hero_id = await resolve_hero(hero)
            return get_aghs_details_logic(hero_id)
        except ValueError as e:
            logger.error(f"Error resolving hero '{hero}': {e}")
            return {"error": str(e)}