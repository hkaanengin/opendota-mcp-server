"""
Player statistics tools
"""
from typing import Dict, Any, Optional, List, Union
import httpx
import logging
from fastmcp import FastMCP
from ..classes import Player
from ..client import fetch_api
from ..utils import get_account_id
from ..resolvers import resolve_hero, resolve_hero_list, resolve_lane, resolve_account_ids, resolve_stat_field

logger = logging.getLogger("opendota-server")


def register_player_tools(mcp: FastMCP):
    """Register all player-related tools with the MCP server"""
    
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
            lane_role = await resolve_lane(lane_role)
            hero_id = await resolve_hero(hero_id)
            included_account_id = await resolve_account_ids(included_account_id)
            against_hero_id = await resolve_hero_list(against_hero_id)
            
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
            lane_role = await resolve_lane(lane_role)
            hero_id = await resolve_hero(hero_id)
            included_account_id = await resolve_account_ids(included_account_id)
            excluded_account_id = await resolve_account_ids(excluded_account_id)
            with_hero_id = await resolve_hero_list(with_hero_id)
            against_hero_id = await resolve_hero_list(against_hero_id)
            
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
            
            result = await fetch_api(f"/players/{account_id}/heroes", params)
            
            # Wrap list response in a dict
            if isinstance(result, list):
                return {"heroes": result}
            return result
            
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
        """
        try:
            account_id = await get_account_id(player_name)
            
            # Resolve all parameters
            lane_role = await resolve_lane(lane_role)
            hero_id = await resolve_hero(hero_id)
            included_account_id = await resolve_account_ids(included_account_id)
            excluded_account_id = await resolve_account_ids(excluded_account_id)
            with_hero_id = await resolve_hero_list(with_hero_id)
            against_hero_id = await resolve_hero_list(against_hero_id)
            
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
            List of statistical totals.
        """
        try:
            account_id = await get_account_id(player_name)
            
            # Resolve all parameters
            lane_role = await resolve_lane(lane_role)
            hero_id = await resolve_hero(hero_id)
            included_account_id = await resolve_account_ids(included_account_id)
            excluded_account_id = await resolve_account_ids(excluded_account_id)
            with_hero_id = await resolve_hero_list(with_hero_id)
            against_hero_id = await resolve_hero_list(against_hero_id)
            
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
            result = await fetch_api(f"/players/{account_id}/totals", params)
            # Wrap list response in a dict
            if isinstance(result, list):
                return {"player_totals": result}
            return result
            
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
            field: Statistical field. Accepts variations like:
                - "kills", "deaths", "assists"
                - "gpm" or "gold_per_min" or "gold per min"
                - "xpm" or "xp_per_min"
                - "cs" or "last_hits"
                - "apm" or "actions_per_min"
                - "damage" or "hero_damage"
                - "healing" or "hero_healing"
                - "lane_efficiency_pct", "level", "pings", "duration"
                - "comeback", "stomp", "loss"
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
            List of histogram buckets.
        """
        try:
            account_id = await get_account_id(player_name)
            
            # Resolve field with fuzzy matching
            field = resolve_stat_field(field)
            
            # Resolve all other parameters
            lane_role = await resolve_lane(lane_role)
            hero_id = await resolve_hero(hero_id)
            included_account_id = await resolve_account_ids(included_account_id)
            excluded_account_id = await resolve_account_ids(excluded_account_id)
            with_hero_id = await resolve_hero_list(with_hero_id)
            against_hero_id = await resolve_hero_list(against_hero_id)
            
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
            
            result = await fetch_api(f"/players/{account_id}/histograms/{field}", params)
            
            # Wrap list response in a dict
            if isinstance(result, list):
                return {"histograms": result}
            return result
            
        except ValueError as e:
            logger.error(f"Error resolving parameter: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error getting histograms for '{player_name}': {e}")
            return {"error": str(e)}