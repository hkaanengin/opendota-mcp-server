"""
Match-related tools
"""
import logging
from fastmcp import FastMCP
from ..client import fetch_api, get_http_client, rate_limiter
from ..config import OPENDOTA_BASE_URL, format_rank_tier
from ..utils import get_account_id
from typing import List, Dict, Any, Union
from ..resolvers import get_hero_by_id_logic, extract_match_sections, process_player_items, build_player_list, build_teamfight_list
from datetime import datetime

logger = logging.getLogger("opendota-server")


def register_match_tools(mcp: FastMCP):
    """Register all match-related tools with the MCP server"""
    
    @mcp.tool()
    async def get_recent_matches(player_name: str) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        Get a player's 20 most recent Dota 2 matches with performance statistics.
        
        Use this when users ask:
        - "Show me [player]'s recent matches"
        - "What are [player]'s last games?"
        - "How has [player] been performing lately?"
        - "Show me [player]'s match history"
        - "What heroes has [player] been playing?"
        - "How did [player] do in their last game?"
        
        Returns detailed statistics for each match including hero played, KDA,
        farm efficiency (GPM/XPM), damage dealt, and more. Useful for analyzing
        recent performance trends and hero picks.
        
        Args:
            player_name: The Dota 2 player name to search for
        
        Returns:
            List of 20 most recent matches (sorted newest first), each containing:
            - match_id (int): Unique match identifier
            - match_date (str): Date match was played (e.g., "December 09, 2024")
            - duration (str): Game length in MM:SS format (e.g., "45:23")
            - game_mode (int): Game mode ID (e.g., 22 for All Pick, 2 for Captain's Mode)
            - hero_name (str): Hero played (e.g., "Rubick", "Anti-Mage")
            - match_rank_tier (str): Skill bracket (e.g., "Ancient [5]", "Divine [3]")
            - kills (int): Number of kills
            - deaths (int): Number of deaths
            - assists (int): Number of assists
            - xp_per_min (int): Experience gained per minute
            - gold_per_min (int): Gold earned per minute
            - hero_damage (int): Total damage dealt to enemy heroes
            - tower_damage (int): Total damage dealt to towers
            - hero_healing (int): Total healing provided to allies
            - last_hits (int): Creeps killed (farming stat)
            
        Common queries:
            - Recent performance: get_recent_matches("kürlo")
            - Check specific player: get_recent_matches("hotpocalypse")
        
        Example:
            get_recent_matches("kürlo")
            -> [
                {
                    "match_id": 8123456789,
                    "match_date": "December 09, 2024",
                    "duration": "45:23",
                    "game_mode": 22,
                    "hero_name": "Rubick",
                    "match_rank_tier": "Divine [3]",
                    "kills": 8,
                    "deaths": 5,
                    "assists": 25,
                    "xp_per_min": 425,
                    "gold_per_min": 380,
                    "hero_damage": 15234,
                    "tower_damage": 1250,
                    "hero_healing": 2340,
                    "last_hits": 45
                },
                ...
            ]
        """
        try:
            account_id = await get_account_id(player_name)
            result = await fetch_api(f"/players/{account_id}/recentMatches")
            logger.info(f"Recent matches for '{player_name}' fetched successfully")

            structured_result = [
                {
                    "match_id": match.get("match_id"),
                    "match_date": datetime.fromtimestamp(match.get("start_time")).strftime("%B %d, %Y"),
                    "duration": f"{match.get('duration', 0) // 60}:{match.get('duration', 0) % 60:02d}",
                    "game_mode": match.get("game_mode"), #maybe add constants for game modes
                    "hero_name": (await get_hero_by_id_logic(match.get("hero_id"))).get("localized_name"),
                    "match_rank_tier": format_rank_tier(match.get("rank_tier")),
                    "kills": match.get("kills"),
                    "deaths": match.get("deaths"),
                    "xp_per_min": match.get("xp_per_min"),
                    "gold_per_min": match.get("gold_per_min"),
                    "assists": match.get("assists"),
                    "hero_damage": match.get("hero_damage"),
                    "tower_damage": match.get("tower_damage"),
                    "hero_healing": match.get("hero_healing"),
                    "last_hits": match.get("last_hits"),
                }
                for match in result
            ]
            return structured_result

        except Exception as e:
            logger.error(f"Error getting recent matches for '{player_name}': {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def request_parse_match(match_id: int) -> Dict[str, Any]:
        """
        Submit a request to parse a specific match for detailed replay analysis.
        
        Use this when users ask:
        - "Parse match [match_id]"
        
        Parsing a match extracts detailed information from the replay including:
        - Teamfight breakdowns (who killed who, where, when)
        - Objectives timeline (tower kills, Roshan, etc.)
        - Gold/XP advantage graphs over time
        - Chat logs
        - Player movement and positioning data
        
        Note: Parsing takes time (usually 1-5 minutes). After requesting parse,
        wait a bit before calling get_match_details() to retrieve the parsed data.
        
        Not all matches can be parsed - very old matches or matches from private
        lobbies may not have replay data available.
        
        Args:
            match_id: The match ID to parse (e.g., 8123456789)
        
        Returns:
            Dictionary containing parse request status:
            - job: Information about the parse job (if queued)
            - status: Current status of the parse request
            - May include error information if parse cannot be queued
            
        Common workflow:
            1. Request parse: request_parse_match(8123456789)
            2. Wait 1-5 minutes
            3. Get parsed data: get_match_details(8123456789)
        
        Example:
            request_parse_match(8123456789)
            -> {
                "job": {
                    "jobId": "12345"
                }
            }
        """
        try:
            client = await get_http_client()
            await rate_limiter.acquire()
            
            response = await client.post(f"{OPENDOTA_BASE_URL}/request/{match_id}")
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Successfully requested parse for match {match_id}")
            
            return result
        except Exception as e:
            logger.error(f"Failed to request parse for match {match_id}: {str(e)}")
            return {"error": str(e)}

    @mcp.tool()
    async def get_match_details(match_id: int) -> Dict[str, Any]:
        """
        Get comprehensive details for a specific match, with automatic detection of parse status.
        
        Use this when users ask:
        - "Show me match [match_id]"
        - "Analyze match [match_id]"
        - "What happened in match [match_id]?"
        - "Show me the teamfights in match [match_id]"
        - "Who won match [match_id]?"
        - "What were the item builds in match [match_id]?"
        - "Show me the gold graph for match [match_id]"
        
        This tool automatically detects whether a match has been parsed (has detailed
        replay data) or not:
        
        - **Parsed matches**: Returns organized summary with teamfights, objectives,
        gold/XP advantage graphs, chat logs, and detailed player performance benchmarks
        - **Unparsed matches**: Returns basic match data with player KDA, GPM/XPM,
        and game outcome
        
        For matches that aren't parsed yet, use request_parse_match() first, wait
        a few minutes, then call this function to get the detailed data.
        
        Args:
            match_id: The match ID to retrieve (e.g., 8123456789)
        
        Returns:
            Dictionary with structure depending on parse status:
            
            If parsed=True (detailed replay data available):
            - parsed (bool): True
            - metadata (dict): Match info (duration, game mode, winner, etc.)
            - teamfights_summary (dict):
                - count (int): Number of teamfights detected
                - teamfights (list): Detailed teamfight breakdowns with:
                    - start/end time, location, deaths, gold swing
            - objectives (list): Timeline of objectives (towers, barracks, Roshan)
            - chat (list): In-game chat messages with timestamps
            - picks_bans (list): Draft phase picks and bans
            - players_summary (dict):
                - count (int): Number of players (always 10)
                - players (list): Per-player statistics including:
                    - account_id, hero_name, team, KDA
                    - gold_per_min, xp_per_min, net_worth
                    - hero_damage, tower_damage, hero_healing
                    - last_hits, denies
                    - benchmarks: Performance percentiles for 7 key metrics
            - gold_advantage (list): Gold advantage over time (array of values)
            - xp_advantage (list): XP advantage over time (array of values)
            
            If parsed=False (basic match data only):
            - parsed (bool): False
            - data (dict):
                - players (list): Basic player stats (KDA, GPM, damage, benchmarks)
                - radiant_win (bool): True if Radiant won, False if Dire won
                - duration (str): Game length in MM:SS format
                - match_id (int): The match ID
        
        Common queries:
            - Basic match info: get_match_details(8123456789)
            - Teamfight analysis: After parsing, check teamfights_summary
            - Performance comparison: Compare benchmarks between players
            - Gold advantage: Check gold_advantage array for momentum swings
        
        Example (parsed match):
            get_match_details(8123456789)
            -> {
                "parsed": true,
                "metadata": {
                    "match_id": 8123456789,
                    "duration": "45:23",
                    "radiant_win": true,
                    "game_mode": 22
                },
                "teamfights_summary": {
                    "count": 12,
                    "teamfights": [
                        {
                            "start": 1245,
                            "end": 1267,
                            "deaths": 6,
                            "gold_delta": 3500,
                            ...
                        }
                    ]
                },
                "players_summary": {
                    "count": 10,
                    "players": [
                        {
                            "hero_name": "Rubick",
                            "team": "radiant",
                            "kills": 8,
                            "deaths": 5,
                            "assists": 25,
                            "gold_per_min": 380,
                            "benchmarks": {
                                "gold_per_min": {"raw": 380, "pct": 65.3},
                                "xp_per_min": {"raw": 425, "pct": 58.2},
                                ...
                            }
                        },
                        ...
                    ]
                },
                "gold_advantage": [0, 200, 450, 800, ...],
                ...
            }
        
        Example (unparsed match):
            get_match_details(8123456789)
            -> {
                "parsed": false,
                "data": {
                    "players": [...],
                    "radiant_win": true,
                    "duration": "45:23",
                    "match_id": 8123456789
                }
            }
        """
        benchmark_fields = [
            "gold_per_min", "xp_per_min", "kills_per_min", 
            "last_hits_per_min", "hero_damage_per_min", 
            "tower_damage", "hero_healing_per_min"
        ]
        try:
            response = await fetch_api(f"/matches/{match_id}")

            # Check if this is a parsed match (has detailed sections)
            # Parsed matches have 'teamfights', 'objectives', 'chat' fields
            is_parsed = ('teamfights' in response or 'objectives' in response or
                        'radiant_gold_adv' in response)

            if is_parsed:
                logger.info(f"Match {match_id} is parsed, returning summarized data")
                sections = extract_match_sections(response)

                raw_teamfights = response.get('teamfights', [])
                raw_players = response.get('players', [])
                formatted_teamfights = await build_teamfight_list(raw_teamfights, raw_players)

                # Build player list with timings (returns dict with players, gold_timings, xp_timings)
                player_data = await build_player_list(sections.get('players', []), benchmark_fields)

                # Return summarized version (same as get_parsed_match_details)
                return {
                    "parsed": True,
                    "metadata": sections.get('metadata', {}),
                    "teamfights_summary": {
                        "count": len(formatted_teamfights),
                        "teamfights": formatted_teamfights
                    },
                    "objectives": sections.get('objectives', []),
                    "chat": sections.get('chat', []),
                    "picks_bans": sections.get('picks_bans', []),
                    "players_summary": {
                        "count": len(player_data['players']),
                        "players": player_data['players']
                    },
                    "gold_advantage": sections.get('radiant_gold_adv', []),
                    "xp_advantage": sections.get('radiant_xp_adv', []),
                    "gold_timings_per_hero": player_data['gold_timings_per_hero'],
                    "xp_timings_per_hero": player_data['xp_timings_per_hero']
                }
            else:
                # Match is NOT parsed - return full data (it's small enough)
                logger.info(f"Match {match_id} is not parsed, returning full data")

                # Build player list with item data
                unparsed_players = []
                for p in response.get("players", []):
                    items_data = await process_player_items(p)

                    player_dict = {
                        "account_id": p.get("account_id"),
                        "player_name": p.get("personaname"),
                        "team_name": "Radiant" if p.get("team_number") == 0 else "Dire",
                        "hero_name": (await get_hero_by_id_logic(p.get("hero_id"))).get("localized_name"),
                        "kills": p.get("kills"),
                        "deaths": p.get("deaths"),
                        "assists": p.get("assists"),
                        "last_hits": p.get("last_hits"),
                        "denies": p.get("denies"),
                        "gold_per_min": p.get("gold_per_min"),
                        "xp_per_min": p.get("xp_per_min"),
                        "net_worth": p.get("net_worth"),
                        "hero_damage": p.get("hero_damage"),
                        "tower_damage": p.get("tower_damage"),
                        "hero_healing": p.get("hero_healing"),
                        "items": items_data,
                        "benchmarks": {
                            field: {
                                "raw": p.get("benchmarks", {}).get(field, {}).get("raw"),
                                "pct": (p.get("benchmarks", {}).get(field, {}).get("pct") or 0) * 100
                            }
                            for field in benchmark_fields
                        },
                    }
                    unparsed_players.append(player_dict)

                structured_response = {
                    "players": unparsed_players,
                    "radiant_win": response.get("radiant_win"),
                    "duration": f"{response.get('duration', 0) // 60}:{response.get('duration', 0) % 60:02d}",
                    "match_id": response.get("match_id"),
                }
                return {
                    "parsed": False,
                    "data": structured_response
                }

        except Exception as e:
            logger.error(f"Error getting match details for {match_id}: {e}")
            return {"error": str(e)}
