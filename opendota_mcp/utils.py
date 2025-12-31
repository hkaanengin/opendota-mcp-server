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
    Get account_id for a player, using static cache if available.

    Checks the pre-populated PLAYER_CACHE first for known players.
    If not found, searches via OpenDota API (does not cache results).

    Args:
        player_name: The player username

    Returns:
        The account_id as string

    Raises:
        ValueError: If player not found
    """
    player_name_lower = player_name.lower()

    # Check static cache first
    if player_name_lower in PLAYER_CACHE:
        return PLAYER_CACHE[player_name_lower]

    # Search via API (not cached)
    client = await get_http_client()
    await rate_limiter.acquire()

    search_response = await client.get(f"{OPENDOTA_BASE_URL}/search?q={player_name}")
    search_response.raise_for_status()

    search_results = search_response.json()
    if not search_results:
        raise ValueError(f"No players found matching '{player_name}'")

    account_id = str(search_results[0]['account_id'])

    return account_id

def load_json(filepath: str) -> Dict[str, Any]:
    """Load JSON file from disk."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
      logger.error(f"Error loading {filepath}: {e}")
      return {}


def load_reference_data():
    """Load reference data from JSON files."""
    import os
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    constants_dir = os.path.join(current_dir, 'constants')
    
    logger.info(f"Loading reference data from: {constants_dir}")

    for const in REFERENCE_DATA.keys():
        filepath = os.path.join(constants_dir, f"{const}.json")
        if os.path.exists(filepath):
            data = load_json(filepath)
            if data:
                REFERENCE_DATA[const] = data
                logger.info(f"Loaded {const}.json successfully ({len(data)} entries)")
            else:
                logger.warning(f"Failed to load or empty: {filepath}")
                REFERENCE_DATA[const] = {}
        else:
            logger.warning(f"File not found: {filepath}")
            REFERENCE_DATA[const] = {}

    logger.info(f"Reference data loaded: {list(REFERENCE_DATA.keys())}")