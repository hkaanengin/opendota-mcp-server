"""
Player statistics tools
"""
from typing import Dict, Any, Optional, List, Union
import asyncio
import httpx
import logging
from datetime import datetime
from fastmcp import FastMCP
from ..classes import Player
from ..client import fetch_api
from ..utils import get_account_id
from ..resolvers import resolve_hero, resolve_hero_list, resolve_lane, resolve_account_ids, resolve_stat_field, get_hero_by_id_logic

logger = logging.getLogger("opendota-server")


def register_player_tools(mcp: FastMCP):
    """Register all player-related tools with the MCP server"""
    
    @mcp.tool()
    async def get_player_info(player_name: str) -> Dict[str, Any]:
        """
        Get complete Dota 2 player profile with overview statistics.
        
        Use this for initial player lookups when users ask:
        - "Who is [player]?"
        - "Tell me about [player]"
        - "What's [player]'s profile?"
        - "Show me [player]'s stats"
        - General player information requests
        
        This is the FIRST tool to use when a user mentions a player - it provides
        a comprehensive overview. For detailed analysis of specific aspects, use
        the specialized tools afterward.
        
        Retrieves:
        - Player profile (name, avatar, profile URL)
        - Overall win/loss statistics and win rate
        - Top 10 most played heroes with individual performance metrics
        
        Args:
            player_name: The Dota 2 player name to search for
            
        Returns:
            Dictionary containing:
            - personaname (str): Player's display name
            - avatarfull (str): URL to player's avatar image
            - profileurl (str): Steam profile URL
            - win_count (int): Total wins
            - lose_count (int): Total losses
            - win_rate (float): Overall win percentage
            - fav_heroes (list): Top 10 heroes, each with:
                - hero_name (str): Hero's display name
                - games_played (int): Games played with this hero
                - win_count (int): Wins with this hero
                - win_rate (float): Win percentage with this hero
        
        Example:
            get_player_info("kürlo")
            -> Full profile with top heroes like Rubick, Invoker, etc.
        """
        try:
            account_id = await get_account_id(player_name)
            player = Player(account_id=account_id)

            # Fetch all three API endpoints in parallel
            logger.info(f"Fetching player data for account_id: {account_id}")
            profile_data, wl_data, heroes_data = await asyncio.gather(
                fetch_api(f"/players/{account_id}"),
                fetch_api(f"/players/{account_id}/wl"),
                fetch_api(f"/players/{account_id}/heroes")
            )

            if 'profile' in profile_data:
                profile = profile_data['profile']
                player.personaname = profile.get('personaname')
                player.avatarfull = profile.get('avatarfull')
                player.profileurl = profile.get('profileurl')

            player.win_count = wl_data.get('win')
            player.lose_count = wl_data.get('lose')
            
            # Build favorite heroes list
            player.fav_heroes = []
            for hero in heroes_data[:10]:
                hero_id = hero.get('hero_id')
                if hero_id is None:
                    continue
                hero_info = await get_hero_by_id_logic(hero_id)
                if "localized_name" not in hero_info:
                    continue
                games_played = hero.get('games', 0)
                win_count = hero.get('win', 0)
                player.fav_heroes.append({
                    "hero_name": hero_info["localized_name"],
                    "games_played": games_played,
                    "win_count": win_count,
                    "win_rate": round((win_count / games_played) * 100, 2) if games_played > 0 else 0.0
                })
            
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
        excluded_account_id: Optional[Union[str, List[str]]] = None,
        with_hero_id: Optional[Union[int, str, List[Union[int, str]]]] = None,
        against_hero_id: Optional[Union[int, str, List[Union[int, str]]]] = None
    ) -> Dict[str, Any]:
        """
        Get simple win/loss counts for a player with optional filters.
        
        Use this when users ask about WIN RATES or WIN/LOSS RECORDS:
        - "What's [player]'s win rate?"
        - "How many games has [player] won?"
        - "What's [player]'s win rate with Rubick?"
        - "How does [player] perform in mid lane?"
        - "What's [player]'s win rate when playing with [teammate]?"
        - "How does [player] do against Pudge?"
        
        Returns ONLY win and loss counts. For detailed hero statistics with dates
        and performance metrics, use get_heroes_played() instead. For aggregate
        statistics like GPM/XPM/KDA, use get_player_totals() instead.
        
        Supports both IDs and natural language for flexible querying.

        Args:
            player_name: The Dota 2 player name to search for
            limit: Number of matches to limit analysis to
            offset: Skip first N matches (for pagination)
            lane_role: Lane filter. Accepts:
                - Integer: 1 (Safe), 2 (Mid), 3 (Off), 4 (Jungle)
                - String: "mid", "safe lane", "offlane", "jungle", "carry", "pos 1", etc.
            hero_id: Hero filter. Accepts:
                - Integer: Hero ID (e.g., 86 for Rubick)
                - String: Hero name (e.g., "Rubick", "Anti-Mage")
            included_account_id: Filter by teammate. Accepts:
                - String: Player name (e.g., "hotpocalypse")
                - List[String]: Multiple player names (games with ANY of these players)
            excluded_account_id: Exclude matches with these players (accepts names or IDs)
            with_hero_id: Require these heroes on player's team (accepts IDs or names)
            against_hero_id: Require these heroes on enemy team. Accepts:
                - Integer/String: Single hero ID or name
                - List: Multiple hero IDs or names
        
        Returns:
            Dictionary with exactly two fields:
            - win (int): Number of wins matching the filters
            - lose (int): Number of losses matching the filters
            
        Common queries:
            - Overall record: get_player_win_loss("kürlo")
            - Hero-specific: get_player_win_loss("kürlo", hero_id="Rubick")
            - Lane-specific: get_player_win_loss("kürlo", lane_role="mid")
            - With teammate: get_player_win_loss("kürlo", included_account_id="hotpocalypse")
            - Vs counter: get_player_win_loss("kürlo", hero_id="Rubick", against_hero_id="Pudge")
        
        Example:
            get_player_win_loss("kürlo", lane_role="mid", hero_id="Rubick")
            -> {"win": 42, "lose": 38}
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
            
            wl_data = await fetch_api(f"/players/{account_id}/wl", params)
            total_games = int(wl_data['win']) + int(wl_data['lose'])
            wl_data["win_rate"] = f"{int(wl_data['win'])/(total_games)*100:.2f}" if total_games > 0 else "0.0"
            return wl_data
            
        except ValueError as e:
            logger.error(f"Error resolving parameter: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error getting win/loss for '{player_name}': {e}")
            return {"error": str(e)}

    @mcp.tool() #Have a look at this. Limit hero etc.
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
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        Get detailed statistics for all heroes a player has played, with performance metrics.
        
        Use this when users ask about HERO POOLS or HERO PERFORMANCE:
        - "What heroes does [player] play?"
        - "Show me [player]'s hero pool"
        - "Which heroes is [player] best at?"
        - "What's [player]'s most played hero?"
        - "How good is [player] at Rubick?"
        - "What heroes does [player] play in mid lane?"
        - "When did [player] last play Invoker?"
        
        This returns detailed stats for EACH hero (win rate, games played, last played date).
        For simple win/loss totals without hero breakdown, use get_player_win_loss() instead.
        
        Supports both IDs and natural language for flexible querying.

        Args:
            player_name: The Dota 2 player name to search for
            limit: Maximum number of heroes to return (default: all heroes)
            offset: Skip first N heroes in results (for pagination)
            lane_role: Filter by lane (accepts "mid", "carry", "offlane", "pos 1-4", etc.)
            hero_id: Focus on specific hero only (accepts name or ID)
            included_account_id: Only include matches with these teammates (accepts names or IDs)
            excluded_account_id: Exclude matches with these players (accepts names or IDs)
            with_hero_id: Require these heroes on player's team (accepts IDs or names, single or list)
            against_hero_id: Require these heroes on enemy team (accepts IDs or names, single or list)
            having: Minimum games played threshold to include a hero in results
        
        Returns:
            List of hero statistics (sorted by games played, descending), each containing:
            - hero_id (str): Hero name (localized, e.g., "Rubick")
            - last_played (str): Date string (e.g., "December 09, 2024")
            - wins (int): Number of wins with this hero
            - games_played (int): Total games with this hero
            - win_rate (str): Win percentage as string (e.g., "65.3")
            
        Common queries:
            - Most played heroes: get_heroes_played("kürlo")
            - Top 5 heroes: get_heroes_played("kürlo", limit=5)
            - Mid lane heroes: get_heroes_played("kürlo", lane_role="mid")
            - Heroes with 10+ games: get_heroes_played("kürlo", having=10)
            - Performance vs Pudge: get_heroes_played("kürlo", against_hero_id="Pudge")
            - Specific hero stats: get_heroes_played("kürlo", hero_id="Rubick")
        
        Example:
            get_heroes_played("kürlo", lane_role="mid", having=5)
            -> [
                {"hero_id": "Rubick", "last_played": "December 09, 2024", "wins": 42, "games_played": 80, "win_rate": "52.5"},
                {"hero_id": "Invoker", "last_played": "December 05, 2024", "wins": 15, "games_played": 25, "win_rate": "60.0"},
                ...
            ]
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
            
            structured_result = []

            for element in result:
                structured_result.append({
                    "hero_id": (await get_hero_by_id_logic(element["hero_id"])).get("localized_name"),
                    "last_played": datetime.fromtimestamp(element.get("last_played")).strftime("%Y-%m-%d"),
                    "wins": element["win"],
                    "games_played": element["games"],
                    "win_rate": f"{int(element['win'])/int(element['games'])*100:.2f}" if element['games'] > 0 else "0.0"
                })

            return structured_result
            
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
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        Get players who frequently play WITH the specified player (teammates, not opponents).
        
        Use this when users ask about TEAMMATES or PARTY MEMBERS:
        - "Who does [player] play with?"
        - "Who are [player]'s teammates?"
        - "What's [player]'s win rate with [teammate]?"
        - "Show me [player]'s most common party members"
        - "Who does [player] duo with?"
        - "Find [player]'s frequent teammates"
        
        This returns players who have been ON THE SAME TEAM as the specified player.
        Results are sorted by number of games played together (most frequent first).
        
        Supports both IDs and natural language for flexible querying.

        Args:
            player_name: The Dota 2 player name to search for
            limit: Number of matches to analyze (default: all recent matches)
            offset: Skip first N matches (for pagination)
            lane_role: Filter to games where player was in specific lane
            hero_id: Filter to games where player played specific hero
            included_account_id: Get stats for SPECIFIC teammate(s) only (accepts names or IDs)
            excluded_account_id: Exclude specific players from results (accepts names or IDs)
            with_hero_id: Filter to games with these heroes on player's team
            against_hero_id: Filter to games against these enemy heroes
            peers_count: Number of teammates to return (default 5, increase for more results)
        
        Returns:
            List of teammate statistics (sorted by games together, descending), each containing:
            - account_id (int): Teammate's account ID
            - personaname (str): Teammate's display name
            - last_played (str): Date of most recent game together (e.g., "December 09, 2024")
            - wins (int): Games won together
            - games_played (int): Total games played together
            - win_rate (str): Win rate as percentage string (e.g., "67.5")
            - average_gpm (float): Player's average GPM when playing with this teammate
            - average_xpm (float): Player's average XPM when playing with this teammate
            
        Common queries:
            - Top teammates: get_player_peers("kürlo", peers_count=10)
            - Specific teammate stats: get_player_peers("kürlo", included_account_id="hotpocalypse")
            - Teammates on Rubick: get_player_peers("kürlo", hero_id="Rubick")
            - Recent duos: get_player_peers("kürlo", limit=100, peers_count=5)
        
        Example:
            get_player_peers("kürlo", peers_count=3)
            -> [
                {"account_id": 123456, "personaname": "hotpocalypse", "last_played": "December 09, 2024", 
                "wins": 45, "games_played": 78, "win_rate": "57.7", "average_gpm": 456.3, "average_xpm": 523.1},
                ...
            ]
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
            
            filtered_peers = peers_data[:peers_count] if peers_count else peers_data
            
            structured_result = []
            for peer in filtered_peers:
                structured_result.append({
                    "account_id": peer["account_id"],
                    "personaname": peer["personaname"],
                    "last_played": datetime.fromtimestamp(peer.get("last_played")).strftime("%Y-%m-%d"),
                    "wins": peer["win"],
                    "games_played": peer["games"],
                    "win_rate": f"{int(peer['win'])/int(peer['games'])*100:.2f}" if peer['games'] > 0 else "0.0",
                    "average_gpm": f"{int(peer.get('with_gpm_sum', 0))/int(peer['with_games']):.2f}" if peer['games'] > 0 else "0.0",
                    "average_xpm": f"{int(peer.get('with_xpm_sum', 0))/int(peer['with_games']):.2f}" if peer['games'] > 0 else "0.0",
                })
            
            return structured_result
        except ValueError as e:
            logger.error(f"Error resolving parameter: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error getting peers for '{player_name}': {e}")
            return {"error": str(e)}

    @mcp.tool() #Have a look at this. Response might be too big.
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
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        Get aggregated performance statistics across ALL tracked metrics (GPM, KDA, damage, etc.).
        
        Use this when users ask about AVERAGE PERFORMANCE or AGGREGATE STATS:
        - "What's [player]'s average GPM?"
        - "How much damage does [player] do per game?"
        - "What's [player]'s average kills per game?"
        - "Show me [player]'s average stats"
        - "What's [player]'s average last hits?"
        - "How much XPM does [player] average?"
        
        Returns comprehensive statistics for ALL fields tracked by OpenDota including:
        - Combat: kills, deaths, assists, kda, hero_kills, hero_damage, hero_healing
        - Economy: gold, gold_per_min, xp_per_min, gold_spent
        - Farming: last_hits, denies, neutral_kills, lane_kills
        - Objectives: tower_damage, tower_kills, courier_kills, observer_uses, sentry_uses
        - And many more...
        
        For simple win/loss counts, use get_player_win_loss() instead.
        For performance distribution analysis, use get_player_histograms() instead.
        
        Supports both IDs and natural language for flexible querying.
        
        Args:
            player_name: The Dota 2 player name to search for
            limit: Number of matches to analyze (default: all available matches)
            offset: Skip first N matches (for pagination)
            lane_role: Filter by lane (accepts "mid", "carry", "pos 1-4", etc.)
            hero_id: Filter to specific hero (accepts name or ID like "Rubick")
            included_account_id: Only include matches with these teammates (accepts names or IDs)
            excluded_account_id: Exclude matches with these players (accepts names or IDs)
            with_hero_id: Require these heroes on player's team (accepts IDs or names)
            against_hero_id: Require these heroes on enemy team (accepts IDs or names)
            having: Minimum games played threshold for included data
        
        Returns:
            List of statistical totals (one object per metric), each containing:
            - field (str): Name of the statistic (e.g., "kills", "gold_per_min", "hero_damage")
            - games_played (int): Number of games in this dataset
            - count (float): Total sum across all games
            - average (float): Mean value per game (count / games_played)
            
        Common queries:
            - All average stats: get_player_totals("kürlo")
            - Mid lane averages: get_player_totals("kürlo", lane_role="mid")
            - Rubick averages: get_player_totals("kürlo", hero_id="Rubick")
            - With teammate: get_player_totals("kürlo", included_account_id="hotpocalypse")
        
        Example:
            get_player_totals("kürlo", hero_id="Rubick", lane_role="mid")
            -> [
                {"field": "kills", "games_played": 80, "count": 418, "average": 5.225},
                {"field": "deaths", "games_played": 80, "count": 520, "average": 6.5},
                {"field": "gold_per_min", "games_played": 80, "count": 33840, "average": 423.0},
                {"field": "hero_damage", "games_played": 80, "count": 1640000, "average": 20500.0},
                ...
            ]
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

            structured_result = []
            for element in result:
                structured_result.append({
                    "field": element["field"],
                    "games_played": element["n"],
                    "count": element["sum"],
                    "average": f"{int(element.get('sum', 0))/int(element['n']):.2f}" if element['n'] > 0 else "0.0"
                })
            
            return structured_result
            
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
    ) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        Get the DISTRIBUTION of a specific statistic across matches (performance consistency analysis).
        
        Use this when users ask about PERFORMANCE RANGES or CONSISTENCY:
        - "How often does [player] get 10+ kills?"
        - "What's [player]'s typical GPM range?"
        - "How consistent is [player]'s farming?"
        - "Show me [player]'s kill distribution"
        - "What GPM does [player] usually achieve?"
        - "How often does [player] get a rampage (5+ kills)?"
        
        This shows HOW OFTEN different values occur (e.g., "30 games with 5-6 kills, 20 games with 7-8 kills").
        
        DO NOT use this for simple averages - use get_player_totals() instead.
        DO NOT use this for win/loss counts - use get_player_win_loss() instead.
        
        Supports both IDs and natural language for flexible querying.
        
        Args:
            player_name: The Dota 2 player name to search for
            field: Statistical field to analyze. Accepts variations like:
                - "kills", "deaths", "assists"
                - "gpm" or "gold_per_min" or "gold per min"
                - "xpm" or "xp_per_min"
                - "cs" or "last_hits"
                - "damage" or "hero_damage"
                - "healing" or "hero_healing"
                - "duration"
                - "comeback", "stomp", "loss"
            limit: Number of matches to analyze (default: all available)
            offset: Skip first N matches (for pagination)
            lane_role: Filter by lane (accepts "mid", "carry", "pos 1-4", etc.)
            hero_id: Filter to specific hero (accepts name or ID)
            included_account_id: Only matches with these teammates (accepts names or IDs)
            excluded_account_id: Exclude matches with these players (accepts names or IDs)
            with_hero_id: Require these heroes on player's team (accepts IDs or names)
            against_hero_id: Require these heroes on enemy team (accepts IDs or names)
            having: Minimum games played threshold
        
        Returns:
            List of histogram buckets showing frequency distribution, each containing:
            - count (int): The value or range (e.g., 10 for "10 kills")
            - games_played (int): Number of games with this value
            - win (int): Games won at this performance level
            - win_rate (str): Win rate at this value (0.0 to 1.0)
            
        The buckets are typically in ranges (e.g., 0-1, 1-2, 2-3 kills) or exact values
        depending on the field. Higher performance levels often correlate with higher win rates.
            
        Common queries:
            - Kill distribution: get_player_histograms("kürlo", field="kills")
            - GPM consistency: get_player_histograms("kürlo", field="gpm")
            - Hero-specific: get_player_histograms("kürlo", field="last_hits", hero_id="Anti-Mage")
        
        Example:
            get_player_histograms("kürlo", field="kills", hero_id="Rubick")
            -> [
                {"count": 0, "games_played": 2, "win": 0, "win_rate": 0.0},
                {"count": 1, "games_played": 5, "win": 1, "win_rate": 0.2},
                {"count": 2, "games_played": 8, "win": 3, "win_rate": 0.375},
                {"count": 3, "games_played": 12, "win": 7, "win_rate": 0.583},
                {"count": 4, "games_played": 15, "win": 10, "win_rate": 0.667},
                {"count": 5, "games_played": 20, "win": 16, "win_rate": 0.8},
                ...
            ]
            
        This tells you: player had 20 games with 5 kills, winning 16 of them (80% win rate at that performance level).
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

            structured_result = []
            for element in result:
                structured_result.append({
                    "count": element["x"],
                    "games_played": element["games"],
                    "win": element["win"],
                    "win_rate": f"{int(element.get('win', 0))/int(element['games'])*100:.2f}" if element['games'] > 0 else "0.0"
                })
            
            return structured_result
            
        except ValueError as e:
            logger.error(f"Error resolving parameter: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error getting histograms for '{player_name}': {e}")
            return {"error": str(e)}