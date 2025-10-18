from fastmcp import FastMCP
import httpx
import logging
import os
from typing import Dict, Any, Optional, List, Union
from .classes import Player, RateLimiter
import json
from difflib import SequenceMatcher

# Setup logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("opendota-server")


mcp = FastMCP("OpenDota API Server")

OPENDOTA_BASE_URL = "https://api.opendota.com/api"

# Initialize rate limiter&HTTP client
rate_limiter = RateLimiter(requests_per_minute=50)
http_client: Optional[httpx.AsyncClient] = None


player_cache : Dict[str, str] = {
    "kürlo": "116856452",
    "ömer": "149733355",
    "hotpocalypse": "79233435",
    "special one": "107409939",
    "xinobillie": "36872251",
    "zøcnutex": "110249858"
}

REFERENCE_DATA: Dict[str, Any] = {
    "heroes": {},
    "item_ids": {},
    "hero_lore": {},
    "aghs_desc": {},
}

# ============================================================================
# LOOKUP TOOLS (Exposed to LLM)
# ============================================================================

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
    
    heroes = await fetch_api("/heroes")
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
        
        # If similarity is high enough (>= 0.8), it's probably the right hero
        if sim >= 0.8:
            matches.append({
                "hero_id": hero['id'],
                "localized_name": hero['localized_name'],
                "similarity": sim
            })
    
    # Sort by similarity
    matches.sort(key=lambda x: x['similarity'], reverse=True)
    
    if matches:
        best_match = matches[0]
        if best_match['similarity'] >= 0.9:
            # Very confident match
            return {
                "hero_id": best_match['hero_id'],
                "localized_name": best_match['localized_name'],
                "match_type": "fuzzy",
                "confidence": "high"
            }
        else:
            # Somewhat confident, but show alternatives
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
        if sim >= 0.5:  # Lower threshold for suggestions
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
    
    lane_mapping = {
        # Safe Lane / Carry / Position 1
        "safe lane": 1, "safelane": 1, "safe": 1, "carry": 1, 
        "pos 1": 1, "position 1": 1, "pos1": 1, "1": 1,
        # Mid Lane / Position 2
        "mid": 2, "midlane": 2, "mid lane": 2, "middle": 2, 
        "pos 2": 2, "position 2": 2, "pos2": 2, "2": 2,
        # Off Lane / Offlane / Position 3
        "off lane": 3, "offlane": 3, "off": 3, "hard lane": 3, "hardlane": 3,
        "pos 3": 3, "position 3": 3, "pos3": 3, "3": 3,
        # Jungle / Position 4
        "jungle": 4, "jungler": 4, "roaming": 4, "roam": 4,
        "pos 4": 4, "position 4": 4, "pos4": 4, "4": 4,
    }
    
    descriptions = {
        1: "Safe Lane (Carry/Position 1)",
        2: "Mid Lane (Position 2)",
        3: "Off Lane (Offlane/Position 3)",
        4: "Jungle/Roaming (Position 4)"
    }
    
    if lane_name_lower in lane_mapping:
        lane_role = lane_mapping[lane_name_lower]
        return {
            "lane_role": lane_role,
            "description": descriptions[lane_role]
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
    heroes = await fetch_api("/heroes")
    
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
    
    return matches[:10]  # Return top 10 matches

# ============================================================================
# INTERNAL RESOLVER FUNCTIONS (Not exposed to LLM)
# ============================================================================

async def _resolve_hero(hero: Optional[Union[int, str]]) -> Optional[int]:
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
        return hero
    
    # It's a string, look it up with fuzzy matching
    result = await get_hero_id_by_name(hero)
    if "error" in result:
        suggestions = result.get("suggestions", [])
        if suggestions:
            raise ValueError(f"Hero '{hero}' not found. Did you mean: {', '.join(suggestions[:3])}?")
        raise ValueError(f"Hero '{hero}' not found")
    
    return result["hero_id"]

async def _resolve_hero_list(heroes: Optional[Union[int, str, List[Union[int, str]]]]) -> Optional[Union[int, List[int]]]:
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
            resolved.append(await _resolve_hero(hero))
        return resolved
    else:
        return await _resolve_hero(heroes)

async def _resolve_lane(lane: Optional[Union[int, str]]) -> Optional[int]:
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
            return lane
        raise ValueError(f"Lane role must be between 1-4, got {lane}")
    
    # It's a string, look it up
    result = await convert_lane_name_to_id(lane)
    if "error" in result:
        valid_options = result.get("valid_options", [])
        raise ValueError(f"Lane '{lane}' not recognized. Valid options: {', '.join(valid_options)}")
    
    return result["lane_role"]

async def _resolve_account_ids(account_ids: Optional[Union[str, List[str]]]) -> Optional[List[int]]:
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

# ============================================================================
# PLAYER STATS TOOLS (With Smart Resolution)
# ============================================================================

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
        account_id = await get_account_id(player_name)
        player = Player(account_id=account_id)
        
        logger.info(f"Fetching player profile for account_id: {account_id}")
        profile_data = await fetch_api(f"/players/{account_id}")
        
        if 'profile' in profile_data:
            profile = profile_data['profile']
            player.personaname = profile.get('personaname')
            player.avatarfull = profile.get('avatarfull')
            player.profileurl = profile.get('profileurl')
        
        logger.info(f"Fetching win/loss stats for account_id: {account_id}")
        wl_data = await fetch_api(f"/players/{account_id}/wl")
        
        player.win_count = wl_data.get('win')
        player.lose_count = wl_data.get('lose')
        player.calculate_win_rate()
        
        logger.info(f"Fetching favorite heroes for account_id: {account_id}")
        heroes_data = await fetch_api(f"/players/{account_id}/heroes")
        
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
    lane_role: Optional[Union[int, str]] = None,
    hero_id: Optional[Union[int, str]] = None,
    included_account_id: Optional[Union[str, List[str]]] = None,
    against_hero_id: Optional[Union[int, str, List[Union[int, str]]]] = None
) -> Dict[str, Any]:
    """
    Get Dota 2 player win/loss statistics with optional filters.
    
    Supports both IDs and natural language for flexible querying.

    Args:
        player_name: The Dota 2 player name to search for.
        limit: Number of matches to limit to.
        offset: The offset for pagination.
        lane_role: Lane filter. Accepts:
            - Integer: 1 (Safe), 2 (Mid), 3 (Off), 4 (Jungle)
            - String: "mid", "safe lane", "offlane", "jungle", "carry", "pos 1", etc.
        hero_id: Hero filter. Accepts:
            - Integer: Hero ID (e.g., 86 for Rubick)
            - String: Hero name (e.g., "Rubick", "Anti-Mage")
        included_account_id: Filter by teammate. Accepts:
            - String: Player name (e.g., "hotpocalypse")
            - List[String]: Multiple player names
        against_hero_id: Filter by enemy hero. Accepts:
            - Integer/String: Single hero ID or name
            - List: Multiple hero IDs or names
    
    Returns:
        Dictionary containing win and loss counts.
    
    Example:
        get_player_win_loss("kürlo", lane_role="mid", hero_id="Rubick", included_account_id=["hotpocalypse"])
    """
    try:
        account_id = await get_account_id(player_name)
        
        # Resolve all parameters
        lane_role = await _resolve_lane(lane_role)
        hero_id = await _resolve_hero(hero_id)
        included_account_id = await _resolve_account_ids(included_account_id)
        against_hero_id = await _resolve_hero_list(against_hero_id)
        
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
        return wl_data
        
    except ValueError as e:
        logger.error(f"Error resolving parameter: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error getting win/loss for '{player_name}': {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_heroes_played(
    player_name: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    lane_role: Optional[Union[int, str]] = None,
    hero_id: Optional[Union[int, str]] = None,
    included_account_id: Optional[Union[str, List[str]]] = None,
    excluded_account_id: Optional[Union[str, List[str]]] = None,
    with_hero_id: Optional[Union[int, str, List[Union[int, str]]]] = None,
    against_hero_id: Optional[Union[int, str, List[Union[int, str]]]] = None,
    having: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get heroes played statistics for the specified Dota 2 player with optional filters.
    
    Supports both IDs and natural language for flexible querying.

    Args:
        player_name: The Dota 2 player name to search for.
        limit: Number of matches to limit to
        offset: Number of matches to offset start by
        lane_role: Lane filter (accepts ID or name like "mid", "carry")
        hero_id: Hero filter (accepts ID or name like "Rubick")
        included_account_id: Filter matches with these teammates (accepts names or IDs)
        excluded_account_id: Filter matches without these players (accepts names or IDs)
        with_hero_id: Heroes on player's team (accepts IDs or names)
        against_hero_id: Heroes against player's team (accepts IDs or names)
        having: The minimum number of games played.
    
    Returns:
        Dictionary containing heroes played with detailed statistics.
    """
    try:
        account_id = await get_account_id(player_name)
        
        # Resolve all parameters
        lane_role = await _resolve_lane(lane_role)
        hero_id = await _resolve_hero(hero_id)
        included_account_id = await _resolve_account_ids(included_account_id)
        excluded_account_id = await _resolve_account_ids(excluded_account_id)
        with_hero_id = await _resolve_hero_list(with_hero_id)
        against_hero_id = await _resolve_hero_list(against_hero_id)
        
        params = {
            k: v for k, v in {
                'limit': limit,
                'offset': offset,
                'lane_role': lane_role,
                'hero_id': hero_id,
                'included_account_id': included_account_id,
                'excluded_account_id': excluded_account_id,
                'with_hero_id': with_hero_id,
                'against_hero_id': against_hero_id,
                'having': having
            }.items() if v is not None
        }
        
        hp_data = await fetch_api(f"/players/{account_id}/heroes", params)
        return hp_data
        
    except ValueError as e:
        logger.error(f"Error resolving parameter: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error getting heroes played for '{player_name}': {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_player_peers(
    player_name: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    lane_role: Optional[Union[int, str]] = None,
    hero_id: Optional[Union[int, str]] = None,
    included_account_id: Optional[Union[str, List[str]]] = None,
    excluded_account_id: Optional[Union[str, List[str]]] = None,
    with_hero_id: Optional[Union[int, str, List[Union[int, str]]]] = None,
    against_hero_id: Optional[Union[int, str, List[Union[int, str]]]] = None,
    peers_count: Optional[int] = 5
) -> Dict[str, Any]:
    """
    Get players who have played with the specified Dota 2 player, with optional filters.
    
    Supports both IDs and natural language for flexible querying.

    Args:
        player_name: The Dota 2 player name to search for.
        limit: Number of matches to limit to.
        offset: Number of matches to offset start by.
        lane_role: Lane filter (accepts ID or name)
        hero_id: Hero filter (accepts ID or name)
        included_account_id: Specific peer(s) to get stats for (accepts names or IDs)
        excluded_account_id: Players to exclude (accepts names or IDs)
        with_hero_id: Heroes on player's team (accepts IDs or names)
        against_hero_id: Heroes against player's team (accepts IDs or names)
        peers_count: Number of peers to return (default 5)
    
    Returns:
        Dictionary containing peer statistics.
        If included_account_id is specified, returns stats for those specific peers.
        Otherwise, returns top N peers by games played together.
    """
    try:
        account_id = await get_account_id(player_name)
        
        # Resolve all parameters
        lane_role = await _resolve_lane(lane_role)
        hero_id = await _resolve_hero(hero_id)
        included_account_id = await _resolve_account_ids(included_account_id)
        excluded_account_id = await _resolve_account_ids(excluded_account_id)
        with_hero_id = await _resolve_hero_list(with_hero_id)
        against_hero_id = await _resolve_hero_list(against_hero_id)
        
        params = {
            k: v for k, v in {
                'limit': limit,
                'offset': offset,
                'lane_role': lane_role,
                'hero_id': hero_id,
                'included_account_id': included_account_id,
                'excluded_account_id': excluded_account_id,
                'with_hero_id': with_hero_id,
                'against_hero_id': against_hero_id
            }.items() if v is not None
        }

        peers_data = await fetch_api(f"/players/{account_id}/peers", params)
        
        if included_account_id is not None:
            return peers_data if peers_data else {"error": "No peers found"}
        else:
            return peers_data[:peers_count]
        
    except ValueError as e:
        logger.error(f"Error resolving parameter: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error getting peers for '{player_name}': {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_player_totals(
    player_name: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    lane_role: Optional[Union[int, str]] = None,
    hero_id: Optional[Union[int, str]] = None,
    included_account_id: Optional[Union[str, List[str]]] = None,
    excluded_account_id: Optional[Union[str, List[str]]] = None,
    with_hero_id: Optional[Union[int, str, List[Union[int, str]]]] = None,
    against_hero_id: Optional[Union[int, str, List[Union[int, str]]]] = None,
    having: Optional[int] = None,
) -> dict:
    """
    Get aggregated statistics and totals for a player.
    
    Supports both IDs and natural language for flexible querying.
    
    Args:
        player_name: The Dota 2 player name to search for.
        limit: Number of matches to limit to
        offset: Number of matches to offset start by
        lane_role: Lane filter (accepts ID or name like "mid")
        hero_id: Hero filter (accepts ID or name like "Rubick")
        included_account_id: Teammates filter (accepts names or IDs)
        excluded_account_id: Players to exclude (accepts names or IDs)
        with_hero_id: Heroes on player's team (accepts IDs or names)
        against_hero_id: Heroes against player's team (accepts IDs or names)
        having: The minimum number of games played.
    
    Returns:
        List of statistical totals with fields like:
        - field: "kills", "deaths", "assists", etc.
        - n: number of matches
        - sum: total value across all matches
    """
    try:
        account_id = await get_account_id(player_name)
        
        # Resolve all parameters
        lane_role = await _resolve_lane(lane_role)
        hero_id = await _resolve_hero(hero_id)
        included_account_id = await _resolve_account_ids(included_account_id)
        excluded_account_id = await _resolve_account_ids(excluded_account_id)
        with_hero_id = await _resolve_hero_list(with_hero_id)
        against_hero_id = await _resolve_hero_list(against_hero_id)
        
        params = {
            k: v for k, v in {
                'limit': limit,
                'offset': offset,
                'lane_role': lane_role,
                'hero_id': hero_id,
                'included_account_id': included_account_id,
                'excluded_account_id': excluded_account_id,
                'with_hero_id': with_hero_id,
                'against_hero_id': against_hero_id,
                'having': having
            }.items() if v is not None
        }
        
        return await fetch_api(f"/players/{account_id}/totals", params)
        
    except ValueError as e:
        logger.error(f"Error resolving parameter: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error getting totals for '{player_name}': {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_player_histograms(
    player_name: str,
    field: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    lane_role: Optional[Union[int, str]] = None,
    hero_id: Optional[Union[int, str]] = None,
    included_account_id: Optional[Union[str, List[str]]] = None,
    excluded_account_id: Optional[Union[str, List[str]]] = None,
    with_hero_id: Optional[Union[int, str, List[Union[int, str]]]] = None,
    against_hero_id: Optional[Union[int, str, List[Union[int, str]]]] = None,
    having: Optional[int] = None,
) -> dict:
    """
    Get distribution of matches for a player in a specific statistical field.
    
    Supports both IDs and natural language for flexible querying.
    
    Args:
        player_name: The Dota 2 player name to search for.
        field: Statistical field (kills, deaths, assists, gold_per_min, xp_per_min, last_hits, 
               lane_efficiency_pct, actions_per_min, level, pings, duration, comeback, stomp, loss)
        limit: Number of results to return
        offset: Number of results to offset
        lane_role: Lane filter (accepts ID or name)
        hero_id: Hero filter (accepts ID or name)
        included_account_id: Teammates filter (accepts names or IDs)
        excluded_account_id: Players to exclude (accepts names or IDs)
        with_hero_id: Heroes on player's team (accepts IDs or names)
        against_hero_id: Heroes against player's team (accepts IDs or names)
        having: The minimum number of games played.
    
    Returns:
        List of histogram buckets with:
        - x: value bucket
        - games: number of games in this bucket
        - win: number of wins in this bucket
    """
    try:
        account_id = await get_account_id(player_name)
        
        # Resolve all parameters
        lane_role = await _resolve_lane(lane_role)
        hero_id = await _resolve_hero(hero_id)
        included_account_id = await _resolve_account_ids(included_account_id)
        excluded_account_id = await _resolve_account_ids(excluded_account_id)
        with_hero_id = await _resolve_hero_list(with_hero_id)
        against_hero_id = await _resolve_hero_list(against_hero_id)
        
        params = {
            k: v for k, v in {
                'limit': limit,
                'offset': offset,
                'lane_role': lane_role,
                'hero_id': hero_id,
                'included_account_id': included_account_id,
                'excluded_account_id': excluded_account_id,
                'with_hero_id': with_hero_id,
                'against_hero_id': against_hero_id,
                'having': having
            }.items() if v is not None
        }
        
        return await fetch_api(f"/players/{account_id}/histograms/{field}", params)
        
    except ValueError as e:
        logger.error(f"Error resolving parameter: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Error getting histograms for '{player_name}': {e}")
        return {"error": str(e)}

# ============================================================================
# EXTRA ENDPOINTS
# ============================================================================

@mcp.tool()
async def get_benchmarks(hero_id: Union[int, str]) -> dict:
    """
    Get statistical benchmarks for a hero (average performance metrics).
    
    Args:
        hero_id: Hero ID or hero name (e.g., 86 or "Rubick")
    
    Returns:
        Benchmark statistics for the hero
    """
    try:
        hero_id = await _resolve_hero(hero_id)
        return await fetch_api("/benchmarks", {"hero_id": hero_id})
    except ValueError as e:
        logger.error(f"Error resolving hero: {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_records(field: str) -> dict:
    """
    Get top performances in a specific statistical field.
    
    Args:
        field: Statistical field (kills, deaths, assists, hero_damage, hero_healing, 
               gold_per_min, xp_per_min, last_hits, lane_efficiency_pct, actions_per_min, 
               level, pings, duration, comeback, stomp, loss)
    
    Returns:
        Top record performances for the specified field
    """
    return await fetch_api(f"/records/{field}")

@mcp.tool()
async def get_scenarios_lane_roles(
    lane_role: Optional[Union[int, str]] = None,
    hero_id: Optional[Union[int, str]] = None,
) -> dict:
    """
    Get win rates for heroes in specific lane roles by time range.
    
    Args:
        lane_role: Lane filter (accepts ID 1-4 or name like "mid")
        hero_id: Hero filter (accepts ID or name like "Rubick")

    Returns:
        List of scenarios with hero_id, lane_role, time (seconds), games, and wins
    """
    try:
        lane_role = await _resolve_lane(lane_role)
        hero_id = await _resolve_hero(hero_id)
        
        params = {k: v for k, v in {'lane_role': lane_role, 'hero_id': hero_id}.items() if v is not None}
        return await fetch_api("/scenarios/laneRoles", params)
        
    except ValueError as e:
        logger.error(f"Error resolving parameter: {e}")
        return {"error": str(e)}

# ============================================================================
# MATCH ENDPOINTS
# ============================================================================

@mcp.tool()
async def get_recent_matches(player_name: str) -> dict:
    """
    Get player's recent matches.
    
    Args:
        player_name: The Dota 2 player name to search for
    
    Returns:
        List of recent match objects with details like match_id, hero_id, kills, deaths, assists, etc.
    """
    try:
        account_id = await get_account_id(player_name)
        return await fetch_api(f"/players/{account_id}/recentMatches")
    except Exception as e:
        logger.error(f"Error getting recent matches for '{player_name}': {e}")
        return {"error": str(e)}

@mcp.tool()
async def request_parse_match(match_id: int) -> dict:
    """
    Submit a new parse request for a specific match
    
    Args:
        match_id: Match ID
    
    Returns:
        Dictionary with parse request status
    """
    client = await get_http_client()
    await rate_limiter.acquire()
    
    response = await client.post(f"{OPENDOTA_BASE_URL}/request/{match_id}")
    response.raise_for_status()
    return response.json()

@mcp.tool()
async def get_match_details(match_id: int) -> dict:
    """
    Get details for a specific match, used for analysing match data in detail.
    
    Args:
        match_id: Match ID
    
    Returns:
        Detailed match information including all players, items, abilities, etc.
    """
    return await fetch_api(f"/matches/{match_id}")

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
    return gh_data

@mcp.tool()
async def get_hero_matchups(hero_id: Union[int, str]) -> dict:
    """
    Get results against other heroes for a specific hero (win/loss rates, counter-picks).
    
    Args:
        hero_id: Hero ID or hero name (e.g., 86 or "Rubick")
    
    Returns:
        Array of matchup objects showing how this hero performs against other heroes.
        Each object contains opponent hero_id, games_played, wins, etc.
        
    Example: Use this to find which heroes counter or are countered by the specified hero.
    """
    try:
        hero_id = await _resolve_hero(hero_id)
        return await fetch_api(f"/heroes/{hero_id}/matchups")
    except ValueError as e:
        logger.error(f"Error resolving hero: {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_hero_item_popularity(hero_id: Union[int, str]) -> dict:
    """
    Get item popularity for a hero categorized by game phase (start, early, mid, late).
    
    Args:
        hero_id: Hero ID or hero name (e.g., 86 or "Rubick")
    
    Returns:
        Object with game phases (start_game_items, early_game_items, mid_game_items, late_game_items).
        Each phase contains items with their popularity counts and win rates.
        
    Example: Use this to understand optimal item builds and timing for a hero.
    """
    try:
        hero_id = await _resolve_hero(hero_id)
        return await fetch_api(f"/heroes/{hero_id}/itemPopularity")
    except ValueError as e:
        logger.error(f"Error resolving hero: {e}")
        return {"error": str(e)}

@mcp.tool()
async def get_hero_stats() -> dict:
    """
    Get aggregated statistics about hero performance in recent matches (win rates, pick rates).
    
    Returns:
        Array of hero statistics including win rates, pick rates, and performance metrics
    """
    return await fetch_api("/heroStats")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

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
    
    if player_name_lower in player_cache:
        return player_cache[player_name_lower]
    
    client = await get_http_client()
    await rate_limiter.acquire()
    
    search_response = await client.get(f"{OPENDOTA_BASE_URL}/search?q={player_name}")
    search_response.raise_for_status()
    
    search_results = search_response.json()
    if not search_results:
        raise ValueError(f"No players found matching '{player_name}'")
    
    account_id = str(search_results[0]['account_id'])
    player_cache[player_name_lower] = account_id
    
    return account_id

async def fetch_api(endpoint: str, params: dict = None) -> dict:
    """
    Fetch data from OpenDota API with rate limiting.
    
    Args:
        endpoint: API endpoint path
        params: Query parameters
    
    Returns:
        JSON response from API
    """
    client = await get_http_client()
    await rate_limiter.acquire()
    
    url = f"{OPENDOTA_BASE_URL}{endpoint}"
    logger.info(f"Fetching data from {url}, with params: {params}")
    
    response = await client.get(url, params=params)
    response.raise_for_status()
    
    logger.info(f"Received response status: {response.status_code}")
    return response.json()

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

async def get_http_client() -> httpx.AsyncClient:
    """Get or create the async HTTP client."""
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
    return http_client

async def cleanup_http_client():
    """Close the HTTP client on shutdown."""
    global http_client
    if http_client is not None:
        await http_client.aclose()
        http_client = None
        logger.info("HTTP client closed")

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
    for const in ['heroes', 'item_ids', 'hero_lore', 'aghs_desc']:
        REFERENCE_DATA[const] = load_json(f"./constants/{const}.json")
    logger.info("Reference data loaded")

if __name__=='__main__':
    logger.info("Starting OpenDota MCP server...")
    
    # Load reference data on startup
    import asyncio
    asyncio.run(load_reference_data())
    
    try:
        mcp.run()
    finally:
        # Cleanup on shutdown
        asyncio.run(cleanup_http_client())
        logger.info("Server shutdown complete")