"""
Internal resolver functions for converting natural language to IDs
"""
from typing import Optional, Union, List
import logging
from .utils import get_account_id
from .config import VALID_STAT_FIELDS

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
    
    # Import here to avoid circular dependency
    from .tools.lookup_tools import get_hero_id_by_name
    
    logger.debug(f"Resolving hero name: '{hero}'")
    
    # It's a string, look it up with fuzzy matching
    result = await get_hero_id_by_name(hero)
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
    
    # Import here to avoid circular dependency
    from .tools.lookup_tools import convert_lane_name_to_id
    
    logger.debug(f"Resolving lane name: '{lane}'")
    
    # It's a string, look it up
    result = await convert_lane_name_to_id(lane)
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