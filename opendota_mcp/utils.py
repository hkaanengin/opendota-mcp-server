"""
Utility functions for OpenDota MCP Server
"""
import json
import logging
from typing import Dict, Any, List
from .config import PLAYER_CACHE, OPENDOTA_BASE_URL, REFERENCE_DATA
from .client import get_http_client, rate_limiter

logger = logging.getLogger("opendota-server")


async def get_account_id(player_name: str) -> str:
    """
    Get account_id for a player, using cache if available.
    
    Args:
        player_name: The player username
        
    Returns:
        The account_id as string
        
    Raises:
        ValueError: If player not found
    """
    player_name_lower = player_name.lower()
    
    if player_name_lower in PLAYER_CACHE:
        return PLAYER_CACHE[player_name_lower]
    
    client = await get_http_client()
    await rate_limiter.acquire()
    
    search_response = await client.get(f"{OPENDOTA_BASE_URL}/search?q={player_name}")
    search_response.raise_for_status()
    
    search_results = search_response.json()
    if not search_results:
        raise ValueError(f"No players found matching '{player_name}'")
    
    account_id = str(search_results[0]['account_id'])
    PLAYER_CACHE[player_name_lower] = account_id
    
    return account_id


def simplify_response(data: Any, remove_keys: List[str] = None) -> Any:
    """
    Simplify API response by removing unnecessary keys.
    
    Args:
        data: The API response data
        remove_keys: List of keys to remove from objects
    
    Returns:
        Simplified data structure
    """
    if remove_keys is None:
        remove_keys = []
    
    if isinstance(data, dict):
        simplified = {k: v for k, v in data.items() if k not in remove_keys}
        for key, value in simplified.items():
            simplified[key] = simplify_response(value, remove_keys)
        return simplified
    
    elif isinstance(data, list):
        return [simplify_response(item, remove_keys) for item in data]
    
    return data


def load_json(filepath: str) -> Dict[str, Any]:
    """Load JSON file from disk."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return {}


async def load_reference_data():
    """Load reference data from JSON files."""
    import os
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    constants_dir = os.path.join(current_dir, 'constants')
    
    logger.info(f"Loading reference data from: {constants_dir}")
    
    for const in ['heroes', 'item_ids', 'hero_lore', 'aghs_desc']:
        filepath = os.path.join(constants_dir, f"{const}.json")
        if os.path.exists(filepath):
            REFERENCE_DATA[const] = load_json(filepath)
            logger.info(f"Loaded {const}.json successfully")
        else:
            logger.warning(f"File not found: {filepath}")
            REFERENCE_DATA[const] = {}
    
    logger.info(f"Reference data loaded: {list(REFERENCE_DATA.keys())}")