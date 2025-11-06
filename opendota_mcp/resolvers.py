"""
Internal resolver functions for converting natural language to IDs
"""
from typing import Optional, Union, List, Dict, Any
import logging
from .utils import get_account_id
from .config import VALID_STAT_FIELDS, REFERENCE_DATA, LANE_MAPPING, LANE_DESCRIPTIONS
from .client import fetch_api
from difflib import SequenceMatcher

logger = logging.getLogger("opendota-server")

async def resolve_hero(hero: Optional[Union[int, str]]) -> Optional[int]:
    """
    Internal: Resolve hero name or ID to hero ID.
    
    Args:
        hero: Hero ID (int) or hero name (str)
    
    Returns:
        Hero ID (int) or None
    
    Raises:
        ValueError: If hero name is not found
    """
    if hero is None:
        return None
    if isinstance(hero, int):
        logger.debug(f"Hero already an ID: {hero}")
        return hero
    
    logger.debug(f"Resolving hero name: '{hero}'")
    
    # It's a string, look it up with fuzzy matching
    result = await get_hero_id_by_name_logic(hero)
    if "error" in result:
        suggestions = result.get("suggestions", [])
        if suggestions:
            raise ValueError(f"Hero '{hero}' not found. Did you mean: {', '.join(suggestions[:3])}?")
        raise ValueError(f"Hero '{hero}' not found")
    
    hero_id = result["hero_id"]
    logger.info(f"RESOLVED: hero '{hero}' -> ID {hero_id} ({result.get('localized_name')})")
    return hero_id


async def resolve_hero_list(heroes: Optional[Union[int, str, List[Union[int, str]]]]) -> Optional[Union[int, List[int]]]:
    """
    Internal: Resolve hero names/IDs to hero IDs (supports lists).
    
    Args:
        heroes: Single hero ID/name or list of hero IDs/names
    
    Returns:
        Single hero ID or list of hero IDs
    """
    if heroes is None:
        return None
    
    if isinstance(heroes, list):
        resolved = []
        for hero in heroes:
            resolved.append(await resolve_hero(hero))
        return resolved
    else:
        return await resolve_hero(heroes)


async def resolve_lane(lane: Optional[Union[int, str]]) -> Optional[int]:
    """
    Internal: Resolve lane name or ID to lane_role ID.
    
    Args:
        lane: Lane role ID (int) or lane name (str)
    
    Returns:
        Lane role ID (int) or None
    
    Raises:
        ValueError: If lane name is not recognized
    """
    if lane is None:
        return None
    if isinstance(lane, int):
        # Validate range
        if 1 <= lane <= 4:
            logger.debug(f"Lane already an ID: {lane}")
            return lane
        raise ValueError(f"Lane role must be between 1-4, got {lane}")
    
    logger.debug(f"Resolving lane name: '{lane}'")
    
    # It's a string, look it up
    result = await convert_lane_name_to_id_logic(lane)
    if "error" in result:
        valid_options = result.get("valid_options", [])
        raise ValueError(f"Lane '{lane}' not recognized. Valid options: {', '.join(valid_options)}")
    
    lane_id = result["lane_role"]
    logger.info(f"RESOLVED: lane '{lane}' -> ID {lane_id} ({result.get('description')})")
    return lane_id


async def resolve_account_ids(account_ids: Optional[Union[str, List[str]]]) -> Optional[List[int]]:
    """
    Internal: Resolve player names to account IDs (supports lists).
    
    Args:
        account_ids: Single player name or list of player names or account IDs
    
    Returns:
        List of account IDs
    """
    if account_ids is None:
        return None
    
    if not isinstance(account_ids, list):
        account_ids = [account_ids]
    
    resolved = []
    for account_id in account_ids:
        if isinstance(account_id, int):
            resolved.append(account_id)
        else:
            # It's a string (player name), look it up
            resolved_id = await get_account_id(str(account_id))
            resolved.append(int(resolved_id))
    
    return resolved


def resolve_stat_field(field: str) -> str:
    """
    Internal: Resolve statistical field name with fuzzy matching.
    
    Handles common variations, abbreviations, and typos.
    
    Args:
        field: Statistical field name (e.g., "gpm", "gold per min", "kills")
    
    Returns:
        Canonical field name
    
    Raises:
        ValueError: If field is not recognized
    
    Examples:
        "gpm" → "gold_per_min"
        "cs" → "last_hits"
        "apm" → "actions_per_min"
        "kill" → "kills"
    """
    if not field:
        raise ValueError("Field cannot be empty")
    
    logger.debug(f"Resolving stat field: '{field}'")
    
    # Normalize input: lowercase, remove extra spaces, underscores to spaces
    field_normalized = field.lower().strip().replace("_", " ").replace("-", " ")
    
    # Try exact match first (after normalization)
    field_key = field_normalized.replace(" ", "_")
    if field_key in VALID_STAT_FIELDS:
        result = VALID_STAT_FIELDS[field_key]
        logger.info(f"RESOLVED: stat field '{field}' -> '{result}'")
        return result
    
    # Try lookup with original (spaces removed)
    field_nospace = field_normalized.replace(" ", "")
    if field_nospace in VALID_STAT_FIELDS:
        result = VALID_STAT_FIELDS[field_nospace]
        logger.info(f"RESOLVED: stat field '{field}' -> '{result}'")
        return result
    
    # Try lookup with spaces
    if field_normalized in VALID_STAT_FIELDS:
        result = VALID_STAT_FIELDS[field_normalized]
        logger.info(f"RESOLVED: stat field '{field}' -> '{result}'")
        return result
    
    # Fuzzy matching: check if field is similar to any valid field
    from difflib import get_close_matches
    
    all_field_variants = list(VALID_STAT_FIELDS.keys())
    close_matches = get_close_matches(field_normalized, all_field_variants, n=3, cutoff=0.6)
    
    if close_matches:
        best_match = close_matches[0]
        canonical_field = VALID_STAT_FIELDS[best_match]
        logger.warning(f"WARNING: Field '{field}' fuzzy matched to '{canonical_field}' (via '{best_match}')")
        return canonical_field
    
    # No match found
    valid_fields = sorted(set(VALID_STAT_FIELDS.values()))
    raise ValueError(
        f"Statistical field '{field}' not recognized. "
        f"Valid fields: {', '.join(valid_fields[:10])}... "
        f"(See documentation for full list)"
    )

async def get_hero_id_by_name_logic(hero_name: str) -> Dict[str, Any]:
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

async def get_hero_by_id_logic(hero_id: int) -> Dict[str, Any]:
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
    
async def convert_lane_name_to_id_logic(lane_name: str) -> Dict[str, Any]:
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


async def resolve_item_name(item_id) -> str:
    def format_item_name(internal_name: str) -> str:
        """Convert internal_name to display format with lowercase articles."""
        words = internal_name.replace("_", " ").split()
        lowercase_words = {'of', 'the', 'and', 'a', 'an', 'in', 'on', 'at', 'to'}
        
        formatted = []
        for i, word in enumerate(words):
            if i == 0 or word not in lowercase_words:
                formatted.append(word.capitalize())
            else:
                formatted.append(word.lower())
        
        return " ".join(formatted)

    if REFERENCE_DATA.get('item_ids'):
        item_id_str = str(item_id)
        if item_id_str in REFERENCE_DATA['item_ids']:
            item_name = REFERENCE_DATA['item_ids'][item_id_str]
            logger.info(f"Found item {item_id} ({item_name}) in reference data")
            return format_item_name(item_name)
        else:
            logger.info(f"Item with ID {item_id} not found in reference data, returning {item_id}")
            return item_id
    else:
        logger.info(f"Item with ID {item_id} not found in reference data, returning {item_id}")
        return item_id