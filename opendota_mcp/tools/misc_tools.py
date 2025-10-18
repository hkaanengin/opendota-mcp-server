"""
Miscellaneous tools (benchmarks, records, scenarios)
"""
from typing import Optional, Union
import logging
from fastmcp import FastMCP #type: ignore
from ..client import fetch_api
from ..resolvers import resolve_hero, resolve_lane, resolve_stat_field

logger = logging.getLogger("opendota-server")


def register_misc_tools(mcp: FastMCP):
    """Register miscellaneous tools with the MCP server"""
    
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
            hero_id = await resolve_hero(hero_id)
            return await fetch_api("/benchmarks", {"hero_id": hero_id})
        except ValueError as e:
            logger.error(f"Error resolving hero: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def get_records(field: str) -> dict:
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
            return await fetch_api(f"/records/{field}")
        except ValueError as e:
            logger.error(f"Error resolving field: {e}")
            return {"error": str(e)}

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
            lane_role = await resolve_lane(lane_role)
            hero_id = await resolve_hero(hero_id)
            
            params = {k: v for k, v in {'lane_role': lane_role, 'hero_id': hero_id}.items() if v is not None}
            return await fetch_api("/scenarios/laneRoles", params)
            
        except ValueError as e:
            logger.error(f"Error resolving parameter: {e}")
            return {"error": str(e)}