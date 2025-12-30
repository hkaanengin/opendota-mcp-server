"""
Configuration and constants for OpenDota MCP Server
"""
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
OPENDOTA_BASE_URL = "https://api.opendota.com/api"

# Optional API key (for higher rate limits)
OPENDOTA_API_KEY: Optional[str] = os.getenv("OPENDOTA_API_KEY") or None

# Default: 50 for anonymous
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
    "items": {},
    "hero_lore": {},
    "aghs_desc": {},
}

# Lane role mappings
LANE_MAPPING = {
    # Safe Lane / Carry / Position 1
    "safe lane": 1, "safelane": 1, "safe": 1, "carry": 1,
    "pos 1": 1, "position 1": 1, "pos1": 1, "1": 1,
    "hard support": 1, "hardsupport": 1, "hard sup": 1, "hardsup":1 , 
    "pos 5": 1, "position 5": 1, "pos5": 1, "5": 1, 
    # Mid Lane / Position 2
    "mid": 2, "midlane": 2, "mid lane": 2, "middle": 2,
    "pos 2": 2, "position 2": 2, "pos2": 2, "2": 2,
    # Off Lane / Offlane / Position 3
    "off lane": 3, "offlane": 3, "off": 3, "hard lane": 3, "hardlane": 3,
    "pos 3": 3, "position 3": 3, "pos3": 3, "3": 3,
    "sot support": 1, "softsupport": 1, "soft sup": 1, "softsup":1 , 
    "pos 4": 1, "position 4": 1, "pos4": 1, "4": 1, 
    # Jungle / Position 4
    # "jungle": 4, "jungler": 4, "roaming": 4, "roam": 4,
    # "pos 4": 4, "position 4": 4, "pos4": 4, "4": 4,
}

LANE_DESCRIPTIONS = {
    1: "Safe Lane (Carry-Position 1/Hard Support-Position 5)",
    2: "Mid Lane (Position 2)",
    3: "Off Lane (Offlane-Position 3/Soft Support-Position 4)",
    4: "Jungle/Roaming (Position 4)"
}

# Valid statistical fields for histograms and records
VALID_STAT_FIELDS = {
    # Combat stats
    "kills": "kills",
    "deaths": "deaths", "death": "deaths",
    "assists": "assists", "assist": "assists",
    
    # Damage and healing
    "hero_damage": "hero_damage", "herodamage": "hero_damage", "damage": "hero_damage",
    "hero_healing": "hero_healing", "herohealing": "hero_healing", "healing": "hero_healing",
    
    # Economy
    "gold_per_min": "gold_per_min", "gpm": "gold_per_min", "goldpermin": "gold_per_min",
    "xp_per_min": "xp_per_min", "xpm": "xp_per_min", "exppermin": "xp_per_min",
    "last_hits": "last_hits", "lasthits": "last_hits", "cs": "last_hits", "creep score": "last_hits",
    "denies": "denies", "denys": "denies", "deny": "denies",

    # Match
    "duration": "duration", "match duration": "duration", "matchduration": "duration", "match_length": "duration", "matchlength": "duration"
}

ITEM_NAME_CONVERSION = {
    "bfury": ["battle fury", "battle furry"],
    "ultimate_scepter": ["aghanims scepter", "aghanim scepter", "aghanim", "agh scepter", "scepter"],
    "shard": ["agh shard", "aghanim shard", "aghanims shard"],
    "hand_of_midas": ["midas", "hands of midas"],
    "guardian_grieves": ["guardians of grieves", "guardian of grieves", "grieves"],
    "spirit_vessel": ["vessel", "spirits vessel", "sprit vessel"],
    "skadi": ["eye of skadi", "eyes of skadi", "eyeofskadi", "eyesofskadi"],
    "black_king_bar": ["bkb", "black king"],
    "monkey_king_bar": ["mkb", "monkey king"],
    "diffusal_blade": ["diffusal"],
    "octarine_core": ["octarine"],
    "travel_boots": ["bot", "bots", "travels", "boots of travel"],
    "power_treads": ["treads", "pt"],
    "phase_boots": ["phase"],
    "tranquil_boots": ["tranquils"]
}

def format_rank_tier(rank_tier):
    if not rank_tier:
        return None
    
    ranks = {
        1: "Herald",
        2: "Guardian",
        3: "Crusader",
        4: "Archon",
        5: "Legend",
        6: "Ancient",
        7: "Divine",
        8: "Immortal",
    }
    
    tier = rank_tier // 10
    stars = min(rank_tier % 10, 5)
    
    if tier == 8:
        return "Immortal"
    
    rank_name = ranks.get(tier, "Unknown")
    return f"{rank_name} {stars}" if rank_name else None
