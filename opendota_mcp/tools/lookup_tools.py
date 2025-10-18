"""
Lookup tools for converting natural language to IDs
"""
from typing import Dict, Any, List
from difflib import SequenceMatcher
import logging
from fastmcp import FastMCP
from ..client import fetch_api
from ..config import LANE_MAPPING, LANE_DESCRIPTIONS, REFERENCE_DATA

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
        def normalize_name(name: str) -> str:
            """Remove spaces, hyphens, apostrophes, make lowercase"""
            return name.lower().replace(" ", "").replace("-", "").replace("'", "")
        
        def similarity(a: str, b: str) -> float:
            """Calculate similarity ratio between two strings"""
            return SequenceMatcher(None, a, b).ratio()
        
        # Use local reference data if available, otherwise fetch from API
        if REFERENCE_DATA.get('heroes'):
            # Convert dict to list format
            heroes = [hero for hero in REFERENCE_DATA['heroes'].values()]
            logger.info(f"Using local reference data with {len(heroes)} heroes")
        else:
            # Fallback to API
            heroes = await fetch_api("/heroes")
            logger.info("Using API data (reference data not loaded)")
        
        hero_name_normalized = normalize_name(hero_name)
        
        # Step 1: Try exact match (normalized)
        for hero in heroes:
            hero_normalized = normalize_name(hero['localized_name'])
            if hero_normalized == hero_name_normalized:
                return {
                    "hero_id": hero['id'],
                    "localized_name": hero['localized_name'],
                    "match_type": "exact"
                }
        
        # Step 2: Try fuzzy match (typos, close matches)
        matches = []
        for hero in heroes:
            hero_normalized = normalize_name(hero['localized_name'])
            sim = similarity(hero_name_normalized, hero_normalized)
            
            if sim >= 0.8:
                matches.append({
                    "hero_id": hero['id'],
                    "localized_name": hero['localized_name'],
                    "similarity": sim
                })
        
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        if matches:
            best_match = matches[0]
            if best_match['similarity'] >= 0.9:
                return {
                    "hero_id": best_match['hero_id'],
                    "localized_name": best_match['localized_name'],
                    "match_type": "fuzzy",
                    "confidence": "high"
                }
            else:
                return {
                    "hero_id": best_match['hero_id'],
                    "localized_name": best_match['localized_name'],
                    "match_type": "fuzzy",
                    "confidence": "medium",
                    "alternatives": [m['localized_name'] for m in matches[:3]]
                }
        
        # Step 3: No good matches, suggest similar heroes
        suggestions = []
        for hero in heroes:
            hero_normalized = normalize_name(hero['localized_name'])
            sim = similarity(hero_name_normalized, hero_normalized)
            if sim >= 0.5:
                suggestions.append({
                    "name": hero['localized_name'],
                    "similarity": sim
                })
        
        suggestions.sort(key=lambda x: x['similarity'], reverse=True)
        
        return {
            "error": f"Hero '{hero_name}' not found",
            "suggestions": [s['name'] for s in suggestions[:5]]
        }
    
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
        lane_name_lower = lane_name.lower().strip()
        
        if lane_name_lower in LANE_MAPPING:
            lane_role = LANE_MAPPING[lane_name_lower]
            return {
                "lane_role": lane_role,
                "description": LANE_DESCRIPTIONS[lane_role]
            }
        
        return {
            "error": f"Lane '{lane_name}' not recognized",
            "valid_options": ["mid", "safe lane", "offlane", "jungle", "pos 1-4"]
        }
    
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
        # Use local reference data if available
        if REFERENCE_DATA.get('heroes'):
            hero_id_str = str(hero_id)
            if hero_id_str in REFERENCE_DATA['heroes']:
                hero_data = REFERENCE_DATA['heroes'][hero_id_str]
                logger.info(f"Found hero {hero_id} ({hero_data.get('localized_name')}) in reference data")
                return hero_data
            else:
                return {
                    "error": f"Hero with ID {hero_id} not found in reference data"
                }
        else:
            # Fallback to API
            heroes = await fetch_api("/heroes")
            for hero in heroes:
                if hero['id'] == hero_id:
                    return hero
            return {
                "error": f"Hero with ID {hero_id} not found"
            }