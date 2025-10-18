"""
Configuration and constants for OpenDota MCP Server
"""
from typing import Dict, Any

# API Configuration
OPENDOTA_BASE_URL = "https://api.opendota.com/api"

# Rate limiting configuration (requests per minute)
RATE_LIMIT_RPM = 50

# Player cache - pre-populated with known players
PLAYER_CACHE: Dict[str, str] = {
    "kürlo": "116856452",
    "ömer": "149733355",
    "hotpocalypse": "79233435",
    "special one": "107409939",
    "xinobillie": "36872251",
    "zøcnutex": "110249858"
}

# Reference data storage
REFERENCE_DATA: Dict[str, Any] = {
    "heroes": {},
    "item_ids": {},
    "hero_lore": {},
    "aghs_desc": {},
}

# Lane role mappings
LANE_MAPPING = {
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

LANE_DESCRIPTIONS = {
    1: "Safe Lane (Carry/Position 1)",
    2: "Mid Lane (Position 2)",
    3: "Off Lane (Offlane/Position 3)",
    4: "Jungle/Roaming (Position 4)"
}

# Valid statistical fields for histograms and records
VALID_STAT_FIELDS = {
    # Combat stats
    "kills": "kills",
    "deaths": "deaths", "death": "deaths",
    "assists": "assists", "assist": "assists",
    "kda": "kills",  # Approximate mapping
    
    # Damage and healing
    "hero_damage": "hero_damage", "herodamage": "hero_damage", "damage": "hero_damage",
    "hero_healing": "hero_healing", "herohealing": "hero_healing", "healing": "hero_healing",
    
    # Economy
    "gold_per_min": "gold_per_min", "gpm": "gold_per_min", "goldpermin": "gold_per_min",
    "xp_per_min": "xp_per_min", "xpm": "xp_per_min", "exppermin": "xp_per_min",
    "last_hits": "last_hits", "lasthits": "last_hits", "cs": "last_hits", "creep score": "last_hits",
    
    # Performance metrics
    "lane_efficiency_pct": "lane_efficiency_pct", "laneefficiency": "lane_efficiency_pct", 
    "lane efficiency": "lane_efficiency_pct",
    "actions_per_min": "actions_per_min", "apm": "actions_per_min", "actionspermin": "actions_per_min",
    
    # Game stats
    "level": "level", "lvl": "level",
    "pings": "pings", "ping": "pings",
    "duration": "duration", "game duration": "duration", "match duration": "duration",
    
    # Game outcome types
    "comeback": "comeback", "comebacks": "comeback",
    "stomp": "stomp", "stomps": "stomp",
    "loss": "loss", "losses": "loss", "lose": "loss",
}

STAT_FIELD_DESCRIPTIONS = {
    "kills": "Number of enemy hero kills",
    "deaths": "Number of times the player died",
    "assists": "Number of assists on enemy hero kills",
    "hero_damage": "Total damage dealt to enemy heroes",
    "hero_healing": "Total healing provided to allied heroes",
    "gold_per_min": "Gold earned per minute (GPM)",
    "xp_per_min": "Experience earned per minute (XPM)",
    "last_hits": "Number of last hits on creeps (CS)",
    "lane_efficiency_pct": "Lane farming efficiency percentage",
    "actions_per_min": "Actions performed per minute (APM)",
    "level": "Final level achieved in the game",
    "pings": "Number of pings used in the game",
    "duration": "Match duration in seconds",
    "comeback": "Games where the team made a comeback",
    "stomp": "Games that were one-sided stomps",
    "loss": "Games that resulted in a loss"
}