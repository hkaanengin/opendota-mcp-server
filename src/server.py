from fastmcp import FastMCP
import httpx
import logging
import os
from typing import Dict, Any
from classes import Player

# Setup logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("opendota-server")


mcp = FastMCP("OpenDota API Server")

OPENDOTA_BASE_URL = "https://api.opendota.com/api"
http_client = httpx.Client(timeout=30.0)

"https://api.opendota.com/api/search?q=Xinobillie"
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
        logger.info(f"Searching for player: {player_name}")
        search_response = await http_client.get(f"{OPENDOTA_BASE_URL}/search?q={player_name}")
        search_response.raise_for_status()
        
        search_results = search_response.json()
        if not search_results:
            return {"error": f"No players found matching '{player_name}'"}
        
        # Get first result's account_id
        account_id = search_results[0]['account_id']
        logger.info(f"Found account_id: {account_id}")
        
        # Initialize Player object
        player = Player(account_id=account_id)
        
        # Step 2: Get player profile info
        logger.info(f"Fetching player profile for account_id: {account_id}")
        profile_response = await http_client.get(f"{OPENDOTA_BASE_URL}/players/{account_id}")
        profile_response.raise_for_status()
        profile_data = profile_response.json()
        
        if 'profile' in profile_data:
            profile = profile_data['profile']
            player.personaname = profile.get('personaname')
            player.name = profile.get('name')
            player.avatarfull = profile.get('avatarfull')
            player.profileurl = profile.get('profileurl')
        
        # Step 3: Get win/loss stats
        logger.info(f"Fetching win/loss stats for account_id: {account_id}")
        wl_response = await http_client.get(f"{OPENDOTA_BASE_URL}/players/{account_id}/wl")
        wl_response.raise_for_status()
        wl_data = wl_response.json()
        
        player.win_count = wl_data.get('win')
        player.lose_count = wl_data.get('lose')
        player.calculate_win_rate()
        
        # Step 4: Get top 5 favorite heroes
        logger.info(f"Fetching favorite heroes for account_id: {account_id}")
        heroes_response = await http_client.get(f"{OPENDOTA_BASE_URL}/players/{account_id}/heroes")
        heroes_response.raise_for_status()
        heroes_data = heroes_response.json()
        
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

