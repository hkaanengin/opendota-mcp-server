"""
Hero-related tools
"""
from typing import Dict, Union, List, Any
import logging
from fastmcp import FastMCP
from ..client import fetch_api
from ..resolvers import resolve_hero, get_item_display_name_by_id, get_hero_by_id_logic

logger = logging.getLogger("opendota-server")


def register_hero_tools(mcp: FastMCP):
    """Register all hero-related tools with the MCP server"""
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
    async def get_hero_matchups(hero: Union[int, str]) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        Get matchup statistics showing how a hero performs against all other heroes.

        Use this when users ask about:
        - "Which heroes counter Pudge?"
        - "What are Anti-Mage's best matchups?"
        - "Show me heroes that Invoker struggles against"
        - "Who should I pick against Phantom Assassin?"
        - "What's Rubick's win rate against Storm Spirit?"

        Returns win/loss statistics for every hero matchup, useful for:
        - Identifying counter-picks (heroes with high win rates against your hero)
        - Finding favorable matchups (heroes your hero performs well against)
        - Draft analysis and hero selection strategy

        Supports fuzzy matching for hero names:
        - "Pudge", "pudge", "PUDGE" all work
        - "Anti-Mage", "antimage", "anti mage" all work
        - "Shadow Fiend", "shadowfiend", "sf" all work

        Args:
            hero: Hero name (display name, internal name, fuzzy match) or hero ID
                  Examples: "Pudge", "antimage", "Shadow Fiend", 86

        Returns:
            List of matchup dictionaries, each containing:
            - hero_name (str): Name of the opponent hero
            - games (int): Total games played in this matchup
            - win (int): Games won against this hero
            - loss (int): Games lost against this hero
            - win_rate (float): Win percentage (0-100) against this hero

            Sorted by game count (most common matchups first)

        Examples:
            get_hero_matchups("Pudge")
            -> [
                {
                    "hero_name": "Anti-Mage",
                    "games": 15234,
                    "win": 7123,
                    "loss": 8111,
                    "win_rate": 46.75
                },
                {
                    "hero_name": "Invoker",
                    "games": 14521,
                    "win": 8234,
                    "loss": 6287,
                    "win_rate": 56.70
                },
                ...
            ]

            get_hero_matchups(86)  # Rubick by ID
            -> Same format as above
        """
        try:
            hero_id = await resolve_hero(hero)
            result = await fetch_api(f"/heroes/{hero_id}/matchups")

            structured_result = []
            for item in result:
                hero_name = await get_hero_by_id_logic(item['hero_id'])
                structured_result.append({
                    'hero_name': hero_name.get("localized_name"),
                    'games': item['games_played'],
                    'win': item['wins'],
                    'loss': item['games_played'] - item['wins'],
                    'win_rate': round((item['wins'] / item['games_played']) * 100, 2) if item['games_played'] > 0 else 0
                })

            return structured_result
        except ValueError as e:
            logger.error(f"Error resolving hero: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def get_hero_item_popularity(hero: Union[int, str]) -> Dict[str, Any]:
        """
        Get item popularity statistics for a hero organized by game phase (start, early, mid, late).

        Use this when users ask about:
        - "What items should I buy on Pudge?"
        - "Show me Anti-Mage's item build"
        - "What's the most popular starting items for Invoker?"
        - "What do people build late game on Phantom Assassin?"
        - "Show me Rubick's core items"

        Returns aggregated item statistics from thousands of matches, useful for:
        - Understanding optimal item progression for a hero
        - Identifying core items vs situational items
        - Learning meta item builds and timings
        - Seeing which items are most popular at each game stage

        Supports fuzzy matching for hero names:
        - "Pudge", "pudge", "PUDGE" all work
        - "Anti-Mage", "antimage", "anti mage" all work
        - "Shadow Fiend", "shadowfiend", "sf" all work

        Args:
            hero: Hero name (display name, internal name, fuzzy match) or hero ID
                  Examples: "Pudge", "antimage", "Shadow Fiend", 86

        Returns:
            Dictionary with game phases as keys, each containing:
            - start_game_items: Items purchased at game start (0-10 min)
            - early_game_items: Items purchased early (0-25 min)
            - mid_game_items: Items purchased mid game (25-40 min)
            - late_game_items: Items purchased late game (40+ min)

            Each phase contains item names mapped to their statistics:
            - wins (int): Times this item was in winning matches
            - games (int): Total matches where this item was purchased

        Examples:
            get_hero_item_popularity("Anti-Mage")
            -> {
                "start_game_items": {
                    "Quelling Blade": {"wins": 15234, "games": 25123},
                    "Tango": {"wins": 18234, "games": 26234},
                    "Slippers of Agility": {"wins": 12345, "games": 21234},
                    ...
                },
                "early_game_items": {
                    "Power Treads": {"wins": 8234, "games": 15234},
                    "Battle Fury": {"wins": 12234, "games": 18234},
                    ...
                },
                "mid_game_items": {
                    "Manta Style": {"wins": 9234, "games": 14234},
                    "Black King Bar": {"wins": 5234, "games": 8234},
                    ...
                },
                "late_game_items": {
                    "Butterfly": {"wins": 4234, "games": 6234},
                    "Abyssal Blade": {"wins": 3234, "games": 5234},
                    ...
                }
            }

            get_hero_item_popularity(1)  # Anti-Mage by ID
            -> Same format as above
        """
        try:
            hero_id = await resolve_hero(hero)
            result = await fetch_api(f"/heroes/{hero_id}/itemPopularity")

            structured_result = {}
            
            for game_phase, items in result.items():
                phase_items = {}
                for item_id, count in items.items():
                    item_name = await get_item_display_name_by_id(item_id)
                    phase_items[item_name] = count
                structured_result[game_phase] = phase_items

            return structured_result
        
        except ValueError as e:
            logger.error(f"Error resolving hero: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error in get_hero_item_popularity: {e}", exc_info=True)
            return {"error": f"Unexpected error: {str(e)}"}
