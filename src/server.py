from fastmcp import FastMCP
import httpx
import logging
import os
from typing import Dict, Any, Optional, List
from .classes import Player

# Setup logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("opendota-server")


mcp = FastMCP("OpenDota API Server")

OPENDOTA_BASE_URL = "https://api.opendota.com/api"
http_client = httpx.Client(timeout=30.0)

player_cache : Dict[str, str] = {
    "kürlo": "116856452",
    "ömer": "149733355",
    "hotpocalypse": "79233435",
    "special one": "107409939",
    "xinobillie": "36872251",
    "zøcnutex": "110249858"
}

@mcp.tool()
async def get_player_info(player_name: str) -> Dict[str, Any]:
    """
    Get complete Dota 2 player information by player name.
    
    Retrieves:
    - Player profile (name, avatar, profile URL)
    - Win/loss statistics and win rate
    - Top 5 most played heroes
    
    Args:
        player_name: The Dota 2 player name to search for
        
    Returns:
        Dictionary containing complete player information
    """
    try:
        # Step 1: Search for player and get account_id
        account_id = await get_account_id(player_name)
        
        player = Player(account_id=account_id)
        
        # Step 2: Get player profile info
        logger.info(f"Fetching player profile for account_id: {account_id}")
        profile_data = await fetch_api(f"/players/{account_id}")
        # profile_response = await http_client.get(f"{OPENDOTA_BASE_URL}/players/{account_id}")
        # profile_response.raise_for_status()
        # profile_data = profile_response.json()
        
        if 'profile' in profile_data:
            profile = profile_data['profile']
            player.personaname = profile.get('personaname')
            player.avatarfull = profile.get('avatarfull')
            player.profileurl = profile.get('profileurl')
        
        # Step 3: Get win/loss stats
        logger.info(f"Fetching win/loss stats for account_id: {account_id}")
        wl_data = await fetch_api(f"/players/{account_id}/wl")
        # wl_response = await http_client.get(f"{OPENDOTA_BASE_URL}/players/{account_id}/wl")
        # wl_response.raise_for_status()
        # wl_data = wl_response.json()
        
        player.win_count = wl_data.get('win')
        player.lose_count = wl_data.get('lose')
        player.calculate_win_rate()
        
        # Step 4: Get top 5 favorite heroes
        logger.info(f"Fetching favorite heroes for account_id: {account_id}")
        heroes_data = await fetch_api(f"/players/{account_id}/heroes")
        # heroes_response = await http_client.get(f"{OPENDOTA_BASE_URL}/players/{account_id}/heroes")
        # heroes_response.raise_for_status()
        # heroes_data = heroes_response.json()
        
        # Get first 5 hero IDs
        top_5_heroes = heroes_data[:5]
        player.fav_heroes = [hero['hero_id'] for hero in top_5_heroes if 'hero_id' in hero]
        
        logger.info(f"Successfully retrieved complete info for {player_name}")
        return player.to_dict()
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error for player '{player_name}': {e}")
        return {"error": f"API error: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Error getting player info for '{player_name}': {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_player_win_loss(
    player_name: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    lane_role: Optional[int] = None,
    hero_id: Optional[int] = None,
    included_account_id: Optional[List[int]] = None,
    against_hero_id: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Get Dota 2 player complete win and loss statistics with optional filters.

    This tool retrieves win and loss counts for a player, with various filters available.

    Args:
        player_name: The Dota 2 player name to search for.
        limit: Number of matches to limit to.
        offset: The offset for pagination.
        lane_role: Filter by lane role 1-4 (1=Safe Lane, 2=Mid, 3=Off Lane, 4=Jungle)
        hero_id: Filter by hero ID.
        included_account_id: Filter by included account ID.
        against_hero_id: Filter by against hero ID.
    
    Returns:
    Dictionary containing win and loss counts.
    """

    try:
        # Search for player and get account_id
        account_id = await get_account_id(player_name)
        
        params = {
            k: v for k, v in {
                'limit': limit,
                'offset': offset,
                'lane_role': lane_role,
                'hero_id': hero_id,
                'included_account_id': included_account_id,
                'against_hero_id': against_hero_id
            }.items() if v is not None
        }
        wl_data = await fetch_api(f"/players/{account_id}/wl", params)
        # wl_response = await http_client.get(
        #     f"{OPENDOTA_BASE_URL}/players/{account_id}/wl",
        #     params=params
        # )
        # wl_response.raise_for_status()
        
        return wl_data
        
    except ValueError as e:
        logger.error(f"Error getting value {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error getting win/loss for '{player_name}': {e}")
        return {"error": str(e)}


@mcp.tool()
async def get_heroes_played(
    player_name: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    lane_role: Optional[int] = None,
    hero_id: Optional[int] = None,
    included_account_id: Optional[List[int]] = None,
    against_hero_id: Optional[List[int]] = None,
    having: Optional[int] = None
    ) -> Dict[str, Any]:
    """
    Get heroes played statistics for the specified Dota 2 player with optional filters.

    Args:
        player_name: The Dota 2 player name to search for.
        limit: Number of matches to limit to
        offset: Number of matches to offset start by
        lane_role: Filter by lane role 1-4 (1=Safe Lane, 2=Mid, 3=Off Lane, 4=Jungle)
        hero_id: Filter by hero ID.
        included_account_id: Filter by included account ID.
        against_hero_id: Filter by against hero ID.
        having: The minimum number of games played.
    
    Returns:
    Dictionary containing heroes played statistics.
    """

    try:
        # Search for player and get account_id
        account_id = await get_account_id(player_name)
        
        params = {
            k: v for k, v in {
                'limit': limit,
                'offset': offset,
                'lane_role': lane_role,
                'hero_id': hero_id,
                'included_account_id': included_account_id,
                'against_hero_id': against_hero_id,
                'having': having
            }.items() if v is not None
        }
        
        hp_data = await fetch_api(f"/players/{account_id}/heroes", params)
        # hp_response = await http_client.get(
        #     f"{OPENDOTA_BASE_URL}/players/{account_id}/heroes",
        #     params=params
        # )
        # hp_response.raise_for_status()
        
        return hp_data
        
    except ValueError as e:
        logger.error(f"Error getting value {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error getting heroes played for '{player_name}': {e}")
        return {"error": str(e)}


@mcp.tool()
async def get_player_peers(
    player_name: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    included_account_id: Optional[List[int]] = None,
    excluded_accout_id: Optional[List[int]] = None,
    against_hero_id: Optional[List[int]] = None,
    peers_count: Optional[int] = 5
    ) -> Dict[str, Any]:
    """
    Get players who have played with the specified Dota 2 player, with optional filters.

    Args:
        player_name: The Dota 2 player name to search for.
        limit: Number of matches to limit to
        offset: Number of matches to offset start by
        included_account_id: Filter by included account ID.
        excluded_accout_id: Filter by excluded account ID.
        against_hero_id: Filter by against hero ID.
        peers_count: Number of peers(most matches played together) to return
    
    Returns:
        Dictionary containing players who have played with the specified Dota 2 player.
        If included_account_id is specified, returns stats for that specific peer(win, games, personnames).
        Otherwise, returns stats for 5 peers withthe most matches played together.
    """
    try:
        account_id = await get_account_id(player_name)
        
        params = {
            k: v for k, v in {
                'limit': limit,
                'offset': offset,
                'included_account_id': included_account_id,
                'excluded_accout_id': excluded_accout_id,
                'against_hero_id': against_hero_id,
                'peers_count': peers_count
            }.items() if v is not None
        }


        peers_data = await fetch_api(f"/players/{account_id}/peers", params)
        # peers_response = await http_client.get(
        #     f"{OPENDOTA_BASE_URL}/players/{account_id}/peers",
        #     params = params)
        # peers_response.raise_for_status()
        # peers_data = peers_response.json()
        
        if included_account_id is not None: #If asked for multiple peers
            if peers_data and len(peers_data) > 0:
                return peers_data[0]
            else:
                return {"error": "No peer found"}
        else:
            return peers_data[:peers_count] #Returns the first 'peers_count' amount
        
    except ValueError as e:
        logger.error(f"Error getting value {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error getting peers for '{player_name}': {e}")
        return {"error": str(e)}

# ============================================================================
# HERO ENDPOINTS
# ============================================================================

@mcp.tool()
async def get_heroes() -> dict:
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
    return await gh_data

@mcp.tool()
async def get_hero_matchups(hero_id: int) -> dict:
    """
    Get results against other heroes for a specific hero (win/loss rates, counter-picks).
    
    Args:
        hero_id: The ID of the hero to get matchup data for
    
    Returns:
        Array of matchup objects, each containing:
        - hero_id (int): The opposing hero's ID
        - hero_name (str): The opposing hero's name (auto-enriched)
        - games_played (int): Number of games played against this hero
        - wins (int): Number of wins against this hero
        - losses (int): Number of losses against this hero
        
    Example: Use this to find which heroes counter or are countered by the specified hero.
    A hero with high wins against another is considered a counter-pick.
    """

    #if hero_id is int/str, fetch from json(condition). Might need it.
    data = await fetch_api(f"/heroes/{hero_id}/matchups")
    return data

@mcp.tool()
async def get_hero_item_popularity(hero_id: int) -> dict:
    """
    Get item popularity for a hero categorized by game phase (start, early, mid, late).
    
    Args:
        hero_id: The ID of the hero
    
    Returns:
        Object with game phases (start_game_items, early_game_items, mid_game_items, late_game_items).
        Each phase contains items with their popularity counts and win rates.
        Example response: {
            "<phase_name>": {
                "<item_id>": "<popularity/count>"
                "<item_id>": "<popularity/count>"
            },
            "<phase_name_2>": {
                "<item_id>": "<popularity/count>"
                "<item_id>": "<popularity/count>"
            },
            ...
        }}
        
    Example: Use this to understand optimal item builds and timing for a hero based on 
    professional game data.
    """
    #if hero_id is int/str, fetch from json(condition). Might need it.
    itemp_data = await fetch_api(f"/heroes/{hero_id}/itemPopularity")
    return await itemp_data


@mcp.tool()
async def get_hero_stats() -> dict: #to do
    """Get aggregated statistics about hero performance in recent matches (win rates, pick rates)."""
    hs_data = await fetch_api("/heroStats")
    return hs_data
# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_account_id(player_name: str) -> str:
    """
    Get account_id for a player, using cache if available.
    
    Args:
        player_name: The player username
        
    Returns:
        The account_id
        
    Raises:
        ValueError: If player not found
    """
    player_name_lower = player_name.lower()
    
    if player_name_lower in player_cache:
        return player_cache[player_name_lower]
    
    search_response = await http_client.get(f"{OPENDOTA_BASE_URL}/search?q={player_name}")
    search_response.raise_for_status()
    
    search_results = search_response.json()
    if not search_results:
        raise ValueError(f"No players found matching '{player_name}'")
    
    account_id = search_results[0]['account_id']
    player_cache[player_name_lower] = account_id
    
    return account_id

def build_query_params(arguments: dict, exclude_keys: list) -> dict:
    """Build query parameters from arguments, excluding specified keys(account_id)."""
    return {k: v for k, v in arguments.items() if k not in exclude_keys and v is not None}

async def fetch_api(endpoint: str, params: dict = None) -> dict:
    """Fetch data from OpenDota API."""
    url = f"{OPENDOTA_BASE_URL}{endpoint}"
    logger.info(f"Fetching data from {url}, with params: {params}")
    response = await http_client.get(url, params=params)
    response.raise_for_status()
    logger.info (f"Received response status: {response.status_code}: ")
    return response.json()

def simplify_response(data: Any, remove_keys: List[str] = None) -> Any:
    """
    Simplify API response by removing unnecessary keys.
    
    Args:
        data: The API response data
        remove_keys: List of keys to remove from objects
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

if __name__=='__main__':
    logger.info("Starting server...")
    mcp.run()