"""
Miscellaneous tools (benchmarks, records, scenarios)
"""
from typing import Optional, Union, List, Dict, Any
import logging
from fastmcp import FastMCP
from ..client import fetch_api
from ..resolvers import resolve_item_to_internal_name, resolve_hero, resolve_lane, resolve_stat_field, get_hero_by_id_logic, get_lane_role_by_id_logic
from datetime import datetime

logger = logging.getLogger("opendota-server")


def register_misc_tools(mcp: FastMCP):
    """Register miscellaneous tools with the MCP server"""
    
    @mcp.tool()
    async def get_benchmarks(hero_id: Union[int, str]) -> Dict[str, Any]:
        """
        Get statistical benchmarks for a hero (average performance metrics across all skill levels).
        
        Use this when users ask:
        - "What are the average stats for [hero]?"
        - "What's a good GPM/XPM for [hero]?"
        - "Show me benchmark stats for [hero]"
        - "What's the typical performance for [hero]?"
        - "How do I compare to other [hero] players?"
        
        Returns percentile-based benchmarks showing what constitutes below-average, average,
        good, and exceptional performance for various metrics on this hero. Useful for
        comparing a player's performance to the general population.
        
        Supports both hero IDs and natural language hero names.
        
        Args:
            hero_id: Hero to get benchmarks for. Accepts:
                - Integer: Hero ID (e.g., 86 for Rubick)
                - String: Hero name (e.g., "Rubick", "Anti-Mage")
        
        Returns:
            Dictionary containing benchmark statistics organized by metric.
            Each metric shows percentile breakdowns (e.g., 0.1, 0.25, 0.5, 0.75, 0.9)
            representing the 10th, 25th, 50th (median), 75th, and 90th percentiles.
            
            Common metrics included:
            - gold_per_min: GPM benchmarks by percentile
            - xp_per_min: XPM benchmarks by percentile
            - kills_per_min, deaths_per_min, assists_per_min: KDA-related benchmarks
            - last_hits_per_min: Farming efficiency benchmarks
            - hero_damage_per_min: Combat effectiveness benchmarks
            - hero_healing_per_min: Support/healing benchmarks
            - tower_damage: Objective damage benchmarks
            - stuns_per_min: Crowd control benchmarks
            - And many more...
            
        Common queries:
            - General benchmarks: get_benchmarks("Rubick")
            - Compare player stats: First get player stats with get_player_totals(),
            then compare to benchmarks from this function
        
        Example:
            get_benchmarks("Rubick")
            -> {
                "gold_per_min": {
                    "0.1": 250.5,   # 10th percentile - below average
                    "0.25": 310.2,  # 25th percentile - low average
                    "0.5": 380.7,   # 50th percentile (median) - average
                    "0.75": 450.3,  # 75th percentile - above average
                    "0.9": 520.8    # 90th percentile - excellent
                },
                "kills_per_min": {
                    "0.1": 0.15,
                    "0.5": 0.35,
                    "0.9": 0.65
                },
                ...
            }
            
        Interpretation: If a player has 460 GPM on Rubick, they're performing around
        the 75th percentile (better than 75% of Rubick players).
        """
        try:
            hero_id = await resolve_hero(hero_id)
            response = await fetch_api("/benchmarks", {"hero_id": hero_id})
            benchmark_results = response.get("result", {})

            return benchmark_results
        except ValueError as e:
            logger.error(f"Error resolving hero: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def get_records(field: str) -> Union[List[Dict[str, Any]], Dict[str, str]]:
        """
        Get top world record performances in a specific statistical field.
        
        Use this when users ask:
        - "What's the world record for most kills in a game?"
        - "Show me the highest GPM ever achieved"
        - "What's the longest Dota 2 game ever?"
        - "Who has the world record for [stat]?"
        - "What are the top performances for [stat]?"
        - "Has anyone ever gotten 50+ kills?"
        
        Returns the all-time best performances globally for the specified metric,
        including match details, hero used, and player information. These are the
        absolute highest values ever recorded in tracked matches.
        
        Supports natural language field names with fuzzy matching and variations.
        
        Args:
            field: Statistical field to get records for. Accepts variations like:
                - Combat: "kills", "deaths", "assists", "kda"
                - Economy: "gold_per_min", "xp_per_min", 
                - Farming: "last_hits", "denies"
                - Damage: "hero_damage", "hero_healing", "tower_damage"
                - Other: "duration"
        
        Returns:
            List of top record performances (sorted by field value, descending), each containing:
            - match_id (int): Match ID for the record game
            - start_time (str): Date of the match (e.g., "December 09, 2024")
            - hero_id (int): Hero ID used in the record
            - hero_name (str): Hero's display name (e.g., "Rubick", "Anti-Mage")
            - score (float): The record value achieved (e.g., 45 kills, 1245 GPM)
            - Additional match details may be included depending on the field
            
        Common queries:
            - Kill record: get_records("kills")
            - GPM record: get_records("gpm") or get_records("gold_per_min")
            - Longest game: get_records("duration")
        
        Example:
            get_records("kills")
            -> [
                {
                    "match_id": 1234567890,
                    "start_time": "March 15, 2024",
                    "hero_id": 1,
                    "hero_name": "Anti-Mage",
                    "score": 45.0,
                    ...
                },
                {
                    "match_id": 9876543210,
                    "start_time": "January 08, 2024",
                    "hero_id": 86,
                    "hero_name": "Rubick",
                    "score": 43.0,
                    ...
                },
                ...
            ]
        """
        try:
            field = resolve_stat_field(field)
            response = await fetch_api(f"/records/{field}")

            updated_response = [
                {**item, 
                "hero_name": (await get_hero_by_id_logic(item["hero_id"])).get('localized_name'),
                "start_time": datetime.fromtimestamp(item.get("start_time")).strftime("%Y-%m-%d")
                }
                for item in response
            ]
            return updated_response
        except ValueError as e:
            logger.error(f"Error resolving field: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}

    @mcp.tool() #Have a look athis. Might be too big of a response.
    async def get_scenarios_lane_roles(
        lane_role: Optional[Union[int, str]] = None,
        hero_name: Optional[Union[int, str]] = None,
    ) -> Dict[str, Any]:
        """
        Get win rates for heroes in specific lane roles segmented by game duration.
        
        Use this when users ask:
        - "What's [hero]'s win rate in mid lane by game time?"
        - "How does [hero] perform in offlane at different game lengths?"
        - "Show me lane role statistics for [hero]"
        - "Which heroes are best in [lane] for long games?"
        - "What's the win rate for mid laners at 30 minutes?"
        - "Does [hero] scale better in late game when played as carry?"
        - "Which lane should I play [hero] in for short games?"
        
        Provides time-segmented win rate data showing how heroes perform in specific
        lanes at different stages of the game. This helps understand which heroes
        thrive in early/mid/late game scenarios and optimal lane choices.
        
        Supports both IDs and natural language for flexible querying.
        
        Args:
            lane_role: Lane to analyze. Accepts:
                - Integer: 1 (Carry-Position 1/Hard Support-Position 5), 2 (Mid), 3 (Offlane-Position 3/Soft Support-Position 4), 4 (Jungle/Support)
                - String: "mid", "safe lane", "offlane", "jungle", "carry", "support" "pos 1-5", etc.
            hero_name: Hero to analyze. Accepts:
                - Integer: Hero ID (e.g., 86 for Rubick)
                - String: Hero name (e.g., "Rubick", "Anti-Mage")
            
            Note: At least one parameter must be provided. You can provide:
            - Only hero_name: See all lanes for this hero by game time
            - Only lane_role: See all heroes in this lane by game time
            - Both: See specific hero in specific lane by game time
        
        Returns:
            Dictionary with structure depending on parameters provided:
            
            If only hero_name provided:
            - hero_name (str): The hero being analyzed
            - [lane_role keys]: One key per lane (e.g., "Safe Lane", "Mid Lane"), each containing:
                - List of timing data with time, games, wins, win_rate
                
            If only lane_role provided:
            - lane_role (str): The lane being analyzed (e.g., "Mid Lane")
            - [hero_name keys]: One key per hero, each containing:
                - List of timing data with time, games, wins, win_rate
                
            If both provided:
            - hero_name (str): The hero
            - lane_role (str): The lane
            - timings (list): List of timing data with time, games, wins, win_rate
            
            Each timing entry contains:
            - time (str): Game duration in MM:SS format (e.g., "25:30")
            - games (int): Number of games at this duration
            - wins (int): Number of wins at this duration
            - win_rate (str): Win percentage as string (e.g., "56.7")
            
        Common queries:
            - Hero in specific lane: get_scenarios_lane_roles(lane_role="mid", hero_name="Rubick")
            - All heroes in lane: get_scenarios_lane_roles(lane_role="mid")
            - Hero in all lanes: get_scenarios_lane_roles(hero_name="Anti-Mage")
        
        Example:
            get_scenarios_lane_roles(lane_role="mid", hero_name="Rubick")
            -> {
                "hero_name": "Rubick",
                "lane_role": "Mid Lane",
                "timings": [
                    {"time": "20:00", "games": 145, "wins": 78, "win_rate": "53.8"},
                    {"time": "30:00", "games": 234, "wins": 125, "win_rate": "53.4"},
                    {"time": "40:00", "games": 189, "wins": 98, "win_rate": "51.9"},
                    {"time": "50:00", "games": 87, "wins": 42, "win_rate": "48.3"},
                    ...
                ]
            }
            
        This shows Rubick's mid lane win rate decreases slightly as games go longer,
        suggesting he's stronger in early-mid game than late game.
        """
        if lane_role is None and hero_name is None:
            return {"error": "Missing required parameters. Please either give a hero name or a lane name"}
        try:
            lane_role = await resolve_lane(lane_role)
            hero_id = await resolve_hero(hero_name)

            response = await fetch_api("/scenarios/laneRoles", {"hero_id": hero_id, "lane_role": lane_role})
            result = {}
            if hero_name and lane_role is None:
                processed_hero_name = (await get_hero_by_id_logic(hero_id)).get("localized_name")
                result["hero_name"] = processed_hero_name
                for element in response:
                    time_key = f"{int(element['time']) // 60}:{int(element['time']) % 60:02d}"
                    lane_role_key = (get_lane_role_by_id_logic(element["lane_role"])).get("lane_role_name")

                    if lane_role_key not in result:
                        result[lane_role_key] = []

                    hero_data = {
                        "time": time_key,
                        "games": element["games"],
                        "wins": element["wins"],
                        "win_rate": f"{int(element['wins'])/int(element['games'])*100:.1f}" if int(element['games']) > 0 else "0.0"
                    }
                    result[lane_role_key].append(hero_data)

                return result
            
            elif lane_role and hero_name is None:
                processed_lane_role = get_lane_role_by_id_logic(lane_role).get("lane_role_name")
                result["lane_role"] = processed_lane_role
                for element in response:
                    time_key = f"{int(element['time']) // 60}:{int(element['time']) % 60:02d}"
                    processed_hero_name = (await get_hero_by_id_logic(element["hero_id"])).get("localized_name")

                    if processed_hero_name not in result:
                        result[processed_hero_name] = []

                    lane_data = {
                        "time": time_key,
                        "games": element["games"],
                        "wins": element["wins"],
                        "win_rate": f"{int(element['wins'])/int(element['games'])*100:.1f}" if int(element['games']) > 0 else "0.0"
                    } 
                    result[processed_hero_name].append(lane_data)

                return result
            elif hero_name and lane_role:
                processed_hero_name = (await get_hero_by_id_logic(hero_id)).get("localized_name")
                processed_lane_role = get_lane_role_by_id_logic(lane_role).get("lane_role_name")
                result["hero_name"] = processed_hero_name
                result["lane_role"] = processed_lane_role
                result["timings"] = []

                for element in response:
                    time_key = f"{int(element['time']) // 60}:{int(element['time']) % 60:02d}"

                    lane_data = {
                        "time": time_key,
                        "games": element["games"],
                        "wins": element["wins"],
                        "win_rate": f"{int(element['wins'])/int(element['games'])*100:.1f}" if int(element['games']) > 0 else "0.0"
                    }
                    result["timings"].append(lane_data)

                return result
            
        except ValueError as e:
            logger.error(f"Error resolving parameter: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def get_scenarios_item_timings(
        item_name: Optional[Union[int, str]] = None,
        hero_name: Optional[Union[int, str]] = None,
    ) -> Dict[str, Any]:
        """
        Get win rates for heroes based on item purchase timing (when key items are completed).
        
        Use this when users ask:
        - "When should I buy [item] on [hero]?"
        - "What's the optimal [item] timing?"
        - "How does [item] timing affect win rate?"
        - "Show me item timing statistics for [hero]"
        - "Which heroes benefit most from early [item]?"
        - "What's a good [item] timing?"
        - "Is [hero] better with early or late [item]?"
        - "When do pros buy [item]?"
        
        Provides time-segmented data showing how item purchase timing correlates with
        win rates. Generally, earlier timings have higher win rates for core items,
        helping identify optimal farming targets and build orders.
        
        Supports natural language item and hero names.
        
        Args:
            item_name: Item to analyze. Accepts item names like:
                - Core items: "bfury" (Battle Fury), "radiance", "midas" (Hand of Midas)
                - Mobility: "blink" (Blink Dagger), "force" (Force Staff)
                - Defense: "bkb" (Black King Bar), "linkens" (Linken's Sphere)
                - Boots: "travels" (Boots of Travel), "phase" (Phase Boots)
                - Support: "wards", "mek" (Mekansm)
                - And many more item names/abbreviations
            hero_name: Hero to analyze. Accepts:
                - Integer: Hero ID (e.g., 86 for Rubick)
                - String: Hero name (e.g., "Rubick", "Anti-Mage")
            
            Note: At least one parameter must be provided. You can provide:
            - Only item_name: See which heroes buy this item and when
            - Only hero_name: See all item timings for this hero
            - Both: See specific item timing for specific hero
        
        Returns:
            Dictionary organized by timing brackets (formatted as "MM:SS").
            Structure depends on parameters provided:
            
            If only item_name provided:
            - item_name (str): The item being analyzed
            - [time brackets]: Keys like "12:30", "15:00", etc., each containing list of:
                - hero_name (str): Hero name
                - games (int): Games with this timing
                - wins (int): Wins with this timing
                - win_rate (str): Win rate percentage (e.g., "65.3")
                
            If only hero_name provided:
            - hero_name (str): The hero being analyzed
            - [time brackets]: Keys like "12:30", "15:00", etc., each containing list of:
                - item_name (str): Item name
                - games (int): Games with this timing
                - wins (int): Wins with this timing
                - win_rate (str): Win rate percentage
                
            If both provided:
            - hero_name (str): The hero
            - item_name (str): The item
            - [time brackets]: Keys like "12:30", "15:00", etc., each containing list of:
                - games (int): Games with this timing
                - wins (int): Wins with this timing
                - win_rate (str): Win rate percentage
        
        Common queries:
            - Optimal item timing: get_scenarios_item_timings(item_name="bfury", hero_name="Anti-Mage")
            - Best heroes for item: get_scenarios_item_timings(item_name="blink")
            - Hero's item timings: get_scenarios_item_timings(hero_name="Anti-Mage")
        
        Example:
            get_scenarios_item_timings(item_name="bfury", hero_name="Anti-Mage")
            -> {
                "hero_name": "Anti-Mage",
                "item_name": "bfury",
                "10:00": [{"games": 12, "wins": 10, "win_rate": "83.3"}],
                "12:00": [{"games": 45, "wins": 32, "win_rate": "71.1"}],
                "15:00": [{"games": 234, "wins": 145, "win_rate": "62.0"}],
                "18:00": [{"games": 189, "wins": 98, "win_rate": "51.9"}],
                "21:00": [{"games": 87, "wins": 38, "win_rate": "43.7"}],
                ...
            }
            
        This clearly shows that Anti-Mage's win rate with Battle Fury decreases
        significantly as the timing gets later. A 12-minute Battle Fury has 71% win rate,
        while an 18-minute Battle Fury only has 52% win rate, suggesting you should
        aim for Battle Fury before 15 minutes for optimal results.
        """
        if item_name is None and hero_name is None:
            return {"error": "Missing required parameters. Please either give a hero name or an item name"}

        try:
            resolved_item_name = await resolve_item_to_internal_name(item_name)
            logger.info(f"Resolved item name: {resolved_item_name}")
            hero_id = await resolve_hero(hero_name)
            logger.info(f"Resolved hero name: {hero_id}")

            response = await fetch_api("/scenarios/itemTimings", {"hero_id": hero_id, "item": resolved_item_name})
            result = {} 
            if item_name and hero_name is None: #If only item_name is provided, organize response by time
                result["item_name"] = resolved_item_name
                for element in response:
                    time_value = int(element['time'])
                    time_key = f"{time_value // 60}:{time_value % 60:02d}"

                    if time_key not in result:
                        result[time_key] = []

                    hero_data = {
                        "hero_name": (await get_hero_by_id_logic(element["hero_id"])).get("localized_name"),
                        "games": element["games"],
                        "wins": element["wins"],
                        "win_rate": f"{int(element['wins'])/int(element['games'])*100:.1f}" if int(element['games']) > 0 else "0.0"
                    }
                    result[time_key].append(hero_data)

                return result
            elif hero_name and item_name is None: #If hero_id is provided, organize response by item_name
                processed_hero_name = (await get_hero_by_id_logic(hero_id)).get("localized_name")
                result["hero_name"] = processed_hero_name

                for element in response:
                    time_value = int(element['time'])
                    time_key = f"{time_value // 60}:{time_value % 60:02d}"

                    if time_key not in result:
                        result[time_key] = []

                    hero_data = {
                        "item_name": element["item"],
                        "games": element["games"],
                        "wins": element["wins"],
                        "win_rate": f"{int(element['wins'])/int(element['games'])*100:.1f}" if int(element['games']) > 0 else "0.0"
                    }
                    result[time_key].append(hero_data)

                return result
            elif hero_name and item_name: #If hero_id and item_name are provided, organize response by time
                processed_hero_name = (await get_hero_by_id_logic(hero_id)).get("localized_name")
                result["hero_name"] = processed_hero_name
                result["item_name"] = resolved_item_name

                for element in response:
                    time_value = int(element['time'])
                    time_key = f"{time_value // 60}:{time_value % 60:02d}"

                    if time_key not in result:
                        result[time_key] = []

                    hero_data = {
                        "games": element["games"],
                        "wins": element["wins"],
                        "win_rate": f"{int(element['wins'])/int(element['games'])*100:.1f}" if int(element['games']) > 0 else "0.0"
                    }
                    result[time_key].append(hero_data)

                return result
            
        except ValueError as e:
            logger.error(f"Error resolving parameter: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}