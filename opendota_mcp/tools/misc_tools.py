"""
Miscellaneous tools (benchmarks, records, scenarios)
"""
from typing import Optional, Union, List, Dict, Any
import logging
from fastmcp import FastMCP
from ..client import fetch_api
from ..resolvers import convert_item_name, resolve_hero, resolve_lane, resolve_stat_field, get_hero_by_id_logic
from datetime import datetime

logger = logging.getLogger("opendota-server")


def register_misc_tools(mcp: FastMCP):
    """Register miscellaneous tools with the MCP server"""
    
    @mcp.tool()
    async def get_benchmarks(hero_id: Union[int, str]) -> Dict[str, Any]:
        """
        Get statistical benchmarks for a hero (average performance metrics).
        
        Args:
            hero_id: Hero ID or hero name (e.g., 86 or "Rubick")
        
        Returns:
            Benchmark statistics for the hero
        """
        try:
            hero_id = await resolve_hero(hero_id)
            response = await fetch_api("/benchmarks", {"hero_id": hero_id})
            benchmark_results = response.get("result", {})

            return benchmark_results
        except ValueError as e:
            logger.error(f"Error resolving hero: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def get_records(field: str) -> List[Dict[str, Any]]:
        """
        Get top performances in a specific statistical field.
        
        Args:
            field: Statistical field. Accepts variations like:
                - "kills", "deaths", "assists"  
                - "gpm" or "gold_per_min"
                - "xpm" or "xp_per_min"
                - "cs" or "last_hits"
                - "apm" or "actions_per_min"
                - "damage" or "hero_damage"
                - "healing" or "hero_healing"
                - "lane_efficiency_pct", "level", "pings", "duration"
                - "comeback", "stomp", "loss"
        
        Returns:
            Top record performances for the specified field
        """
        try:
            field = resolve_stat_field(field)
            response = await fetch_api(f"/records/{field}")

            updated_response = [
                {**item, 
                "hero_name": get_hero_by_id_logic(item["hero_id"]).get('localized_name'),
                "start_time": datetime.fromtimestamp(item.get("start_time")).strftime("%B %d, %Y")
                }
                for item in response
            ]
            return updated_response
        except ValueError as e:
            logger.error(f"Error resolving field: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def get_scenarios_lane_roles(
        lane_role: Optional[Union[int, str]] = None,
        hero_name: Optional[Union[int, str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get win rates for heroes in specific lane roles by time range.
        
        Args:
            lane_role: Lane filter (accepts ID 1-4 or name like "mid")
            hero_name: Hero filter (accepts name like "Rubick")

        Returns:
            List of scenarios with hero_name, lane_role, time (seconds), games, and wins
        """
        if lane_role is None and hero_name is None:
            return {"error": "Missing required parameters. Please either give a hero name or an item name"}
        try:
            lane_role = await resolve_lane(lane_role)
            hero_id = await resolve_hero(hero_name)

            response = await fetch_api("/scenarios/laneRoles", {"hero_id": hero_id, "lane_role": lane_role})
            result = {}
            if hero_id and lane_role is None:
                processed_hero_name = (await get_hero_by_id_logic(hero_id)).get("localized_name")
                result["hero_name"] = processed_hero_name
                
                
                return result
            
        except ValueError as e:
            logger.error(f"Error resolving parameter: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def get_scenarios_item_timings(
        item_name: Optional[Union[int, str]] = None,
        hero_name: Optional[Union[int, str]] = None,
    ) -> Dict[str, Any]:
        """
        Get win rates for heroes in specific item timings by time range.
        
        Args:
            item_name: Item filter (accepts name like "bfury")
            hero_name: Hero filter (accepts name like "Rubick")

        Returns:
            List of scenarios with hero_name, item_name, time (seconds), games, and wins
        """
        if item_name is None and hero_name is None:
            return {"error": "Missing required parameters. Please either give a hero name or an item name"}

        try:
            resolved_item_name = convert_item_name(item_name)
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
                        "win_rate": f"{int(element['wins'])/int(element['games'])*100:.1f}"
                    }
                    result[time_key].append(hero_data)

                return result
            elif hero_name and item_name is None: #If hero_id is provided, organize response by item_name
                processed_hero_name = (await get_hero_by_id_logic(hero_id)).get("localized_name") #check this if works.
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
                        "win_rate": f"{int(element['wins'])/int(element['games'])*100:.1f}"
                    }
                    result[time_key].append(hero_data)

                return result
            elif hero_name and item_name: #If hero_id and item_name are provided, organize response by time
                processed_hero_name = (await get_hero_by_id_logic(hero_id)).get("localized_name") #check this if works.
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
                        "win_rate": f"{int(element['wins'])/int(element['games'])*100:.1f}"
                    }
                    result[time_key].append(hero_data)

                return result
            
        except ValueError as e:
            logger.error(f"Error resolving parameter: {e}")
            return {"error": str(e)}