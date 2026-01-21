from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import time
from collections import defaultdict

logger = logging.getLogger("opendota-server")

@dataclass
class Player:
    account_id: int
    personaname: Optional[str] = None
    avatarfull: Optional[str] = None
    profileurl: Optional[str] = None
    win_count: Optional[int] = None
    lose_count: Optional[int] = None
    fav_heroes: Optional[List[Dict[str, Any]]] = None

    @property
    def win_rate(self) -> Optional[float]:
        """Calculate win rate from win and lose counts"""
        if self.win_count is not None and self.lose_count is not None:
            total = self.win_count + self.lose_count
            if total > 0:
                return round((self.win_count / total) * 100, 2)
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert Player to dictionary, removing None values"""
        data = asdict(self)
        # Add computed win_rate property
        data['win_rate'] = self.win_rate
        return {k: v for k, v in data.items() if v is not None}

# Rate limiter configuration
class RateLimiter:
    """
    Simple rate limiter for OpenDota API.
    OpenDota has rate limits: 60 requests per minute for anonymous users.
    """
    def __init__(self, requests_per_minute: int = 50):
        """
        Args:
            requests_per_minute: Maximum requests allowed per minute (default 50 to be safe)
        """
        self.requests_per_minute = requests_per_minute
        self.requests = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait if necessary to respect rate limits."""
        async with self.lock:
            now = datetime.now()
            # Remove requests older than 1 minute
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < timedelta(minutes=1)]
            
            if len(self.requests) >= self.requests_per_minute:
                # Calculate wait time
                oldest_request = self.requests[0]
                wait_time = 60 - (now - oldest_request).total_seconds()
                if wait_time > 0:
                    logger.warning(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
                    await asyncio.sleep(wait_time)
                    # Clean up again after waiting
                    now = datetime.now()
                    self.requests = [req_time for req_time in self.requests 
                                   if now - req_time < timedelta(minutes=1)]
            
            # Add current request
            self.requests.append(now)

# Server Metrics for server.py
class ServerMetrics:
    """Simple in-memory metrics for debugging"""
    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.tool_calls = defaultdict(int)
        self.errors = []
        self.last_requests = []
        self.active_connections = 0
        
    def record_request(self, method: str, path: str):
        self.request_count += 1
        self.last_requests.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "path": path
        })
        # Keep only last 50 requests
        if len(self.last_requests) > 50:
            self.last_requests.pop(0)
    
    def record_tool_call(self, tool_name: str):
        self.tool_calls[tool_name] += 1
    
    def record_error(self, error: str, context: str = None):
        self.errors.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(error),
            "context": context
        })
        # Keep only last 100 errors
        if len(self.errors) > 100:
            self.errors.pop(0)

    @property
    def uptime(self) -> float:
        """Get server uptime in seconds"""
        return time.time() - self.start_time

    def to_dict(self):
        return {
            "uptime_seconds": round(self.uptime, 2),
            "total_requests": self.request_count,
            "tool_calls": dict(self.tool_calls),
            "recent_errors": self.errors[-10:],  # Last 10 errors
            "last_requests": self.last_requests[-10:],  # Last 10 requests
            "active_connections": self.active_connections
        }


class ObjectiveProcessor:
    """Processes match objectives into human-readable format."""

    # Building key patterns: (pattern, readable_name)
    BUILDING_PATTERNS = [
        ("tower1", "T1"), ("tower2", "T2"), ("tower3", "T3"), ("tower4", "T4"),
        ("melee_rax", "Melee Rax"), ("range_rax", "Ranged Rax"), ("fort", "Ancient"),
    ]

    LANE_PATTERNS = [("_bot", "Bot"), ("_mid", "Mid"), ("_top", "Top")]

    def __init__(self, slot_to_hero: Dict[int, str]):
        self.slot_to_hero = slot_to_hero
        # Map objective types to handler methods
        self.handlers = {
            "CHAT_MESSAGE_FIRSTBLOOD": self._handle_firstblood,
            "CHAT_MESSAGE_COURIER_LOST": self._handle_courier,
            "building_kill": self._handle_building,
            "CHAT_MESSAGE_MINIBOSS_KILL": self._handle_tormentor,
            "CHAT_MESSAGE_ROSHAN_KILL": self._handle_roshan,
            "CHAT_MESSAGE_AEGIS": self._handle_aegis,
        }

    def process(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single objective into structured format."""
        obj_type = obj.get("type", "")
        handler = self.handlers.get(obj_type, self._handle_unknown)
        result = handler(obj)
        result["time"] = self._format_time(obj.get("time", 0))
        return result

    def _format_time(self, seconds: int) -> str:
        mins, secs = divmod(seconds, 60)
        return f"{mins}:{secs:02d}"

    def _get_team_from_slot(self, slot: Optional[int]) -> str:
        return "radiant" if slot is not None and slot < 128 else "dire"

    def _get_hero(self, slot: Optional[int]) -> str:
        return self.slot_to_hero.get(slot, "Unknown")

    def _parse_building(self, key: str) -> tuple:
        """Returns (building_name, benefiting_team, building_type)."""
        team_prefix = "Radiant" if "goodguys" in key else "Dire"
        benefiting = "dire" if "goodguys" in key else "radiant"

        # Find building type and category
        building = next((name for pattern, name in self.BUILDING_PATTERNS if pattern in key), "Building")

        # Determine building category
        if building == "Ancient":
            return f"{team_prefix} {building}", benefiting, "ancient"
        elif "Rax" in building:
            building_type = "barracks"
        elif building.startswith("T"):
            building_type = "tower"
        else:
            building_type = "building"

        # Find lane
        lane = next((name for pattern, name in self.LANE_PATTERNS if pattern in key), "")
        return f"{team_prefix} {building} {lane}".strip(), benefiting, building_type

    def _parse_unit(self, unit: str) -> str:
        if "npc_dota_hero_" in unit:
            hero_internal = unit.replace("npc_dota_hero_", "")
            return " ".join(w.capitalize() for w in hero_internal.split("_"))
        return "Creeps" if any(x in unit for x in ["creep", "siege"]) else "Unknown"

    def _handle_firstblood(self, obj: Dict) -> Dict:
        slot = obj.get("player_slot")
        return {
            "type": "first_blood",
            "description": f"First Blood by {self._get_hero(slot)}",
            "team": self._get_team_from_slot(slot),
        }

    def _handle_courier(self, obj: Dict) -> Dict:
        losing_team = "radiant" if obj.get("team") == 2 else "dire"
        benefiting = "dire" if losing_team == "radiant" else "radiant"
        killer_slot = obj.get("killer", -1)
        killer = f" by {self._get_hero(killer_slot)}" if killer_slot >= 0 else ""
        return {
            "type": "courier",
            "description": f"{losing_team.capitalize()} Courier killed{killer}",
            "team": benefiting,
        }

    def _handle_building(self, obj: Dict) -> Dict:
        building_name, team, building_type = self._parse_building(obj.get("key", ""))
        destroyer = self._parse_unit(obj.get("unit", ""))
        return {
            "type": building_type,
            "description": f"{building_name} destroyed by {destroyer}",
            "team": team,
        }

    def _handle_tormentor(self, obj: Dict) -> Dict:
        slot = obj.get("player_slot")
        return {
            "type": "tormentor",
            "description": f"Tormentor killed by {self._get_hero(slot)}",
            "team": self._get_team_from_slot(slot),
        }

    def _handle_roshan(self, obj: Dict) -> Dict:
        team = "radiant" if obj.get("team") == 2 else "dire"
        return {
            "type": "roshan",
            "description": f"Roshan killed by {team.capitalize()}",
            "team": team,
        }

    def _handle_aegis(self, obj: Dict) -> Dict:
        slot = obj.get("player_slot")
        return {
            "type": "aegis",
            "description": f"Aegis taken by {self._get_hero(slot)}",
            "team": self._get_team_from_slot(slot),
        }

    def _handle_unknown(self, obj: Dict) -> Dict:
        obj_type = obj.get("type", "unknown")
        logger.warning(f"Unknown objective type: {obj_type}")
        return {
            "type": obj_type.lower().replace("chat_message_", ""),
            "description": obj_type,
            "team": "unknown",
            "raw": obj,
        }