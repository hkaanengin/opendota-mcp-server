"""
Match-related tools
"""
import logging
from fastmcp import FastMCP
from ..client import fetch_api, get_http_client, rate_limiter
from ..config import OPENDOTA_BASE_URL, format_rank_tier
from ..utils import get_account_id
from typing import List, Dict, Any
from ..resolvers import get_hero_by_id_logic, extract_match_sections
from datetime import datetime

logger = logging.getLogger("opendota-server")


def register_match_tools(mcp: FastMCP):
    """Register all match-related tools with the MCP server"""
    
    @mcp.tool()
    async def get_recent_matches(player_name: str) -> List[Dict[str, Any]]:
        """
        Get player's recent matches. Returns 20 matches by default.
        
        Args:
            player_name: The Dota 2 player name to search for
        
        Returns:
            List of recent match objects with details like match_id, hero_id, kills, deaths, assists, etc.
        """
        try:
            account_id = await get_account_id(player_name)
            result = await fetch_api(f"/players/{account_id}/recentMatches")

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
    async def get_match_details(match_id: int) -> Dict[str, Any]:
        """
        Get details for a specific match, used for analysing match data in detail.

        Automatically detects if match is parsed and returns summarized data if needed.
        For unparsed matches, returns full data. For parsed matches with detailed stats,
        returns organized summary with teamfights, objectives, and player performance.

        Args:
            match_id: Match ID

        Returns:
            Match information - either full data (unparsed) or summarized sections (parsed)
        """
        try:
            response = await fetch_api(f"/matches/{match_id}")

            # Check if this is a parsed match (has detailed sections)
            # Parsed matches have 'teamfights', 'objectives', 'chat' fields
            is_parsed = ('teamfights' in response or 'objectives' in response or
                        'radiant_gold_adv' in response)

            if is_parsed:
                logger.info(f"Match {match_id} is parsed, returning summarized data")
                sections = extract_match_sections(response)

                # Return summarized version (same as get_parsed_match_details)
                return {
                    "parsed": True,
                    "metadata": sections.get('metadata', {}),
                    "teamfights_summary": {
                        "count": len(sections.get('teamfights', [])),
                        "teamfights": sections.get('teamfights', [])
                    },
                    "objectives": sections.get('objectives', []),
                    "chat": sections.get('chat', []),
                    "picks_bans": sections.get('picks_bans', []),
                    "players_summary": {
                        "count": len(sections.get('players', [])),
                        "players": [
                            {
                                "account_id": p.get("account_id"),
                                "player_slot": p.get("player_slot"),
                                "hero_id": p.get("hero_id"),
                                "hero_name": (await get_hero_by_id_logic(p.get("hero_id"))).get("localized_name"),
                                "personaname": p.get("personaname"),
                                "team": "radiant" if p.get("player_slot", 0) < 128 else "dire",
                                "kills": p.get("kills"),
                                "deaths": p.get("deaths"),
                                "assists": p.get("assists"),
                                "gold_per_min": p.get("gold_per_min"),
                                "xp_per_min": p.get("xp_per_min"),
                                "net_worth": p.get("net_worth"),
                                "hero_damage": p.get("hero_damage"),
                                "tower_damage": p.get("tower_damage"),
                                "hero_healing": p.get("hero_healing"),
                                "last_hits": p.get("last_hits"),
                                "denies": p.get("denies"),
                                "benchmarks": p.get("benchmarks", {}),
                            }
                            for p in sections.get('players', [])
                        ]
                    },
                    "gold_advantage": sections.get('radiant_gold_adv', []),
                    "xp_advantage": sections.get('radiant_xp_adv', []),
                }
            else:
                # Match is NOT parsed - return full data (it's small enough)
                logger.info(f"Match {match_id} is not parsed, returning full data")
                return {
                    "parsed": False,
                    "data": response
                }

        except Exception as e:
            logger.error(f"Error getting match details for {match_id}: {e}")
            return {"error": str(e)}
