"""
Lookup tools for converting natural language to IDs
"""
from typing import Dict, Any, List, Union
import logging
from fastmcp import FastMCP
from ..client import fetch_api
from ..config import REFERENCE_DATA
from ..resolvers import resolve_hero, resolve_item_to_internal_name, get_item_details_logic, get_aghs_details_logic

logger = logging.getLogger("opendota-server")


def register_lookup_tools(mcp: FastMCP):
    """Register all lookup tools with the MCP server"""
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
            internal_name = await resolve_item_to_internal_name(item_name)

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