"""
Internal resolver functions for converting natural language to IDs
"""
from typing import Optional, Union, List, Dict, Any
import logging
from .utils import get_account_id
from .config import VALID_STAT_FIELDS, REFERENCE_DATA, LANE_MAPPING, LANE_DESCRIPTIONS, ITEM_NAME_CONVERSION
from .client import fetch_api
from difflib import SequenceMatcher, get_close_matches

logger = logging.getLogger("opendota-server")

# Fuzzy matching thresholds
SIMILARITY_THRESHOLD_HIGH = 0.9  # High confidence match
SIMILARITY_THRESHOLD_MEDIUM = 0.8  # Good match
SIMILARITY_THRESHOLD_FUZZY = 0.7  # Fuzzy match (allows 1-2 char typos)
SIMILARITY_THRESHOLD_STAT_FIELD = 0.6  # Stat field matching
SIMILARITY_THRESHOLD_SUGGESTION = 0.5  # For showing suggestions


def _normalize_name(name: str) -> str:
    """Remove spaces, hyphens, apostrophes, make lowercase"""
    return name.lower().replace(" ", "").replace("-", "").replace("'", "")


def _similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, a, b).ratio()

async def resolve_hero(hero: Optional[Union[int, str]]) -> Optional[int]:
    """
    Internal: Resolve hero name or ID to hero ID.
    
    Args:
        hero: Hero ID (int) or hero name (str)
    
    Returns:
        Hero ID (int) or None
    
    Raises:
        ValueError: If hero name is not found
    """
    if hero is None:
        return None
    if isinstance(hero, int):
        logger.debug(f"Hero already an ID: {hero}")
        return hero
    
    logger.debug(f"Resolving hero name: '{hero}'")
    
    # It's a string, look it up with fuzzy matching
    result = await get_hero_id_by_name_logic(hero)
    if "error" in result:
        suggestions = result.get("suggestions", [])
        if suggestions:
            raise ValueError(f"Hero '{hero}' not found. Did you mean: {', '.join(suggestions[:3])}?")
        raise ValueError(f"Hero '{hero}' not found")
    
    hero_id = result["hero_id"]
    logger.info(f"RESOLVED: hero '{hero}' -> ID {hero_id} ({result.get('localized_name')})")
    return hero_id

async def resolve_hero_list(heroes: Optional[Union[int, str, List[Union[int, str]]]]) -> Optional[Union[int, List[int]]]:
    """
    Internal: Resolve hero names/IDs to hero IDs (supports lists).
    
    Args:
        heroes: Single hero ID/name or list of hero IDs/names
    
    Returns:
        Single hero ID or list of hero IDs
    """
    if heroes is None:
        return None
    
    if isinstance(heroes, list):
        resolved = []
        for hero in heroes:
            resolved.append(await resolve_hero(hero))
        return resolved
    else:
        return await resolve_hero(heroes)

async def resolve_lane(lane: Optional[Union[int, str]]) -> Optional[int]:
    """
    Internal: Resolve lane name or ID to lane_role ID.
    
    Args:
        lane: Lane role ID (int) or lane name (str)
    
    Returns:
        Lane role ID (int) or None
    
    Raises:
        ValueError: If lane name is not recognized
    """
    if lane is None:
        return None
    if isinstance(lane, int):
        # Validate range
        if 1 <= lane <= 4:
            logger.debug(f"Lane already an ID: {lane}")
            return lane
        raise ValueError(f"Lane role must be between 1-4, got {lane}")
    
    logger.debug(f"Resolving lane name: '{lane}'")
    
    # It's a string, look it up
    result = convert_lane_name_to_id_logic(lane)
    if "error" in result:
        valid_options = result.get("valid_options", [])
        raise ValueError(f"Lane '{lane}' not recognized. Valid options: {', '.join(valid_options)}")
    
    lane_id = result["lane_role"]
    logger.info(f"RESOLVED: lane '{lane}' -> ID {lane_id} ({result.get('description')})")
    return lane_id

async def resolve_account_ids(account_ids: Optional[Union[str, List[str]]]) -> Optional[List[int]]:
    """
    Internal: Resolve player names to account IDs (supports lists).
    
    Args:
        account_ids: Single player name or list of player names or account IDs
    
    Returns:
        List of account IDs
    """
    if account_ids is None:
        return None
    
    if not isinstance(account_ids, list):
        account_ids = [account_ids]
    
    resolved = []
    for account_id in account_ids:
        if isinstance(account_id, int):
            resolved.append(account_id)
        else:
            # It's a string (player name), look it up
            resolved_id = await get_account_id(str(account_id))
            resolved.append(int(resolved_id))
    
    return resolved

def resolve_stat_field(field: str) -> str:
    """
    Internal: Resolve statistical field name with fuzzy matching.
    
    Handles common variations, abbreviations, and typos.
    
    Args:
        field: Statistical field name (e.g., "gpm", "gold per min", "kills")
    
    Returns:
        Canonical field name
    
    Raises:
        ValueError: If field is not recognized
    
    Examples:
        "gpm" → "gold_per_min"
        "cs" → "last_hits"
        "apm" → "actions_per_min"
        "kill" → "kills"
    """
    if not field:
        raise ValueError("Field cannot be empty")
    
    logger.debug(f"Resolving stat field: '{field}'")
    
    # Normalize input: lowercase, remove extra spaces, underscores to spaces
    field_normalized = field.lower().strip().replace("_", " ").replace("-", " ")
    
    # Try exact match first (after normalization)
    field_key = field_normalized.replace(" ", "_")
    if field_key in VALID_STAT_FIELDS:
        result = VALID_STAT_FIELDS[field_key]
        logger.info(f"RESOLVED: stat field '{field}' -> '{result}'")
        return result
    
    # Try lookup with original (spaces removed)
    field_nospace = field_normalized.replace(" ", "")
    if field_nospace in VALID_STAT_FIELDS:
        result = VALID_STAT_FIELDS[field_nospace]
        logger.info(f"RESOLVED: stat field '{field}' -> '{result}'")
        return result
    
    # Try lookup with spaces
    if field_normalized in VALID_STAT_FIELDS:
        result = VALID_STAT_FIELDS[field_normalized]
        logger.info(f"RESOLVED: stat field '{field}' -> '{result}'")
        return result
    
    # Fuzzy matching: check if field is similar to any valid field
    all_field_variants = list(VALID_STAT_FIELDS.keys())
    close_matches = get_close_matches(field_normalized, all_field_variants, n=3, cutoff=SIMILARITY_THRESHOLD_STAT_FIELD)

    if close_matches:
        best_match = close_matches[0]
        canonical_field = VALID_STAT_FIELDS[best_match]
        logger.warning(f"WARNING: Field '{field}' fuzzy matched to '{canonical_field}' (via '{best_match}')")
        return canonical_field
    
    # No match found
    valid_fields = sorted(set(VALID_STAT_FIELDS.values()))
    raise ValueError(
        f"Statistical field '{field}' not recognized. "
        f"Valid fields: {', '.join(valid_fields[:10])}... "
        f"(See documentation for full list)"
    )

async def get_hero_id_by_name_logic(hero_name: str) -> Dict[str, Any]:
    """
    Find a hero's ID by name with fuzzy matching for typos and case variations.
    Use this when you need to convert hero names to IDs.

    Args:
        hero_name: The hero name (handles typos, case variations, spaces)

    Returns:
        Dictionary with hero_id and hero name, or suggestions if not found

    Examples:
        - "Rubick", "rubick", "RUBICK", "rubik" all return Rubick's ID
        - "Anti-Mage", "anti mage", "antimage" all work
        - "rbick" returns Rubick with fuzzy matching
    """
    # Use local reference data if available, otherwise fetch from API
    if REFERENCE_DATA.get('heroes'):
        # Convert dict to list format
        heroes = [hero for hero in REFERENCE_DATA['heroes'].values()]
        logger.info(f"Using local reference data with {len(heroes)} heroes")
    else:
        # Fallback to API
        heroes = await fetch_api("/heroes")
        logger.info("Using API data (reference data not loaded)")

    hero_name_normalized = _normalize_name(hero_name)

    # Step 1: Try exact match (normalized)
    for hero in heroes:
        hero_normalized = _normalize_name(hero['localized_name'])
        if hero_normalized == hero_name_normalized:
            return {
                "hero_id": hero['id'],
                "localized_name": hero['localized_name'],
                "match_type": "exact"
            }

    # Step 2: Try fuzzy match (typos, close matches)
    matches = []
    for hero in heroes:
        hero_normalized = _normalize_name(hero['localized_name'])
        sim = _similarity(hero_name_normalized, hero_normalized)

        if sim >= SIMILARITY_THRESHOLD_MEDIUM:
            matches.append({
                "hero_id": hero['id'],
                "localized_name": hero['localized_name'],
                "similarity": sim
            })

    matches.sort(key=lambda x: x['similarity'], reverse=True)

    if matches:
        best_match = matches[0]
        if best_match['similarity'] >= SIMILARITY_THRESHOLD_HIGH:
            return {
                "hero_id": best_match['hero_id'],
                "localized_name": best_match['localized_name'],
                "match_type": "fuzzy",
                "confidence": "high"
            }
        else:
            return {
                "hero_id": best_match['hero_id'],
                "localized_name": best_match['localized_name'],
                "match_type": "fuzzy",
                "confidence": "medium",
                "alternatives": [m['localized_name'] for m in matches[:3]]
            }

    # Step 3: No good matches, suggest similar heroes
    suggestions = []
    for hero in heroes:
        hero_normalized = _normalize_name(hero['localized_name'])
        sim = _similarity(hero_name_normalized, hero_normalized)
        if sim >= SIMILARITY_THRESHOLD_SUGGESTION:
            suggestions.append({
                "name": hero['localized_name'],
                "similarity": sim
            })

    suggestions.sort(key=lambda x: x['similarity'], reverse=True)

    return {
        "error": f"Hero '{hero_name}' not found",
        "suggestions": [s['name'] for s in suggestions[:5]]
    }

async def get_hero_by_id_logic(hero_id: int) -> Dict[str, Any]:
    """
    Get detailed hero information by hero ID.
    Returns complete hero data including stats, attributes, and roles.
    
    Args:
        hero_id: The hero's ID (e.g., 1 for Anti-Mage)
    
    Returns:
        Dictionary with complete hero information including:
        - Basic info (name, localized_name, roles)
        - Attributes (str, agi, int and their gains)
        - Stats (health, mana, armor, attack, movement)
        - Combat info (attack range, attack rate, vision)
    
    Example:
        get_hero_by_id(1) returns all data for Anti-Mage
    """
    # Use local reference data if available
    if REFERENCE_DATA.get('heroes'):
        hero_id_str = str(hero_id)
        if hero_id_str in REFERENCE_DATA['heroes']:
            hero_data = REFERENCE_DATA['heroes'][hero_id_str]
            logger.info(f"Found hero {hero_id} ({hero_data.get('localized_name')}) in reference data")
            return hero_data
        else:
            return {
                "error": f"Hero with ID {hero_id} not found in reference data"
            }
    else:
        # Fallback to API
        heroes = await fetch_api("/heroes")
        for hero in heroes:
            if hero['id'] == hero_id:
                logger.info(f"Found hero {hero_id} ({hero.get('localized_name')}) via API")
                return hero
        return {
            "error": f"Hero with ID {hero_id} not found"
        }
    
def convert_lane_name_to_id_logic(lane_name: str) -> Dict[str, Any]:
    """
    Convert lane/position names to lane_role IDs.
    Use this when you need to convert natural language lanes to IDs.
    
    Args:
        lane_name: Lane name like "mid", "safe lane", "offlane", "jungle", "carry", "pos 1", etc.
    
    Returns:
        Dictionary with lane_role ID and description
    
    Examples:
        - "mid", "midlane", "pos 2" all return lane_role 2
        - "carry", "safe lane", "pos 1" all return lane_role 1
        - "offlane", "offline", "pos 3" all return lane_role 3
    """
    lane_name_lower = lane_name.lower().strip()
    
    if lane_name_lower in LANE_MAPPING:
        lane_role = LANE_MAPPING[lane_name_lower]
        return {
            "lane_role": lane_role,
            "description": LANE_DESCRIPTIONS[lane_role]
        }
    
    return {
        "error": f"Lane '{lane_name}' not recognized",
        "valid_options": ["mid", "safe lane", "offlane", "jungle", "pos 1-4"]
    }

async def get_item_display_name_by_id(item_id: Union[int, str]) -> str:
    def format_item_name(internal_name: str) -> str:
        """Convert internal_name to display format with lowercase articles."""
        words = internal_name.replace("_", " ").split()
        lowercase_words = {'of', 'the', 'and', 'a', 'an', 'in', 'on', 'at', 'to'}
        
        formatted = []
        for i, word in enumerate(words):
            if i == 0 or word not in lowercase_words:
                formatted.append(word.capitalize())
            else:
                formatted.append(word.lower())
        
        return " ".join(formatted)

    if REFERENCE_DATA.get('item_ids'):
        item_id_str = str(item_id)
        if item_id_str in REFERENCE_DATA['item_ids']:
            item_name = REFERENCE_DATA['item_ids'][item_id_str]
            logger.info(f"Found item {item_id} ({item_name}) in reference data")
            return format_item_name(item_name)
        else:
            logger.info(f"Item with ID {item_id} not found in reference data, returning {item_id}")
            return item_id
    else:
        logger.info(f"Item with ID {item_id} not found in reference data, returning {item_id}")
        return item_id

async def resolve_item_to_internal_name(item_input: str) -> str:
    """
    Resolve item display name or fuzzy name to internal name.

    Args:
        item_input: Display name (e.g., "Diffusal Blade", "Octarine Core")
                   or fuzzy input (e.g., "diffusal", "octarine")

    Returns:
        Internal item name (e.g., "diffusal_blade", "octarine_core")

    Raises:
        ValueError: If item not found with suggestions
    """
    if item_input is None:
        return None

    if not REFERENCE_DATA.get('items'):
        raise ValueError("Items reference data not loaded")

    items = REFERENCE_DATA['items']
    input_normalized = _normalize_name(item_input)

    # Step 1: Check ITEM_NAME_CONVERSION for known aliases
    for internal_name, aliases in ITEM_NAME_CONVERSION.items():
        for alias in aliases:
            if _normalize_name(alias) == input_normalized:
                logger.info(f"Matched '{item_input}' to '{internal_name}' via alias")
                return internal_name

    # Step 2: Try exact match on internal name (e.g., "diffusal_blade")
    for key in items.keys():
        if _normalize_name(key) == input_normalized:
            logger.info(f"Exact match: '{item_input}' → '{key}'")
            return key

    # Step 3: Try exact match on display name (e.g., "Diffusal Blade")
    for internal_name, item_data in items.items():
        dname = item_data.get('dname', '')
        if _normalize_name(dname) == input_normalized:
            logger.info(f"Display name match: '{item_input}' → '{internal_name}'")
            return internal_name

    # Step 4: Fuzzy match on both internal names and display names
    matches = []
    for internal_name, item_data in items.items():
        dname = item_data.get('dname', '')

        # Score against internal name
        internal_sim = _similarity(input_normalized, _normalize_name(internal_name))
        # Score against display name
        display_sim = _similarity(input_normalized, _normalize_name(dname))

        best_sim = max(internal_sim, display_sim)

        if best_sim >= SIMILARITY_THRESHOLD_FUZZY:
            matches.append({
                'internal_name': internal_name,
                'display_name': dname,
                'similarity': best_sim
            })

    if matches:
        # Sort by similarity, highest first
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        best_match = matches[0]

        logger.info(f"Fuzzy match: '{item_input}' → '{best_match['internal_name']}' (similarity: {best_match['similarity']:.2f})")
        return best_match['internal_name']

    # Step 5: No match found - provide suggestions
    suggestions = [item_data.get('dname', key) for key, item_data in list(items.items())[:5]]
    raise ValueError(f"Item '{item_input}' not found. Example items: {', '.join(suggestions)}")

async def get_item_details_logic(item_internal_name: str) -> Dict[str, Any]:
    """
    Get item details from items.json using internal name.

    Args:
        item_internal_name: Internal item name (e.g., "diffusal_blade")

    Returns:
        Complete item data dictionary
    """
    if not REFERENCE_DATA.get('items'):
        return {"error": "Items reference data not loaded"}

    if item_internal_name in REFERENCE_DATA['items']:
        item_details = REFERENCE_DATA['items'][item_internal_name]
        logger.info(f"Found item '{item_internal_name}' in reference data")
        return item_details
    else:
        logger.error(f"Item '{item_internal_name}' not found in items.json")
        return {"error": f"Item '{item_internal_name}' not found"}

def get_aghs_details_logic(hero_id: int) -> Dict[str, Any]:
    """
    Get Aghanim's Scepter and Shard details for a hero from aghs_desc.json.

    Args:
        hero_id: Hero ID (e.g., 1 for Anti-Mage)

    Returns:
        Dictionary with scepter and shard information:
        - hero_id: Hero ID
        - hero_name: Internal hero name
        - has_scepter: Whether hero has scepter upgrade
        - scepter_desc: Scepter description (if has_scepter)
        - scepter_skill_name: Affected skill name (if has_scepter)
        - scepter_new_skill: Whether scepter adds new skill (if has_scepter)
        - has_shard: Whether hero has shard upgrade
        - shard_desc: Shard description (if has_shard)
        - shard_skill_name: Affected skill name (if has_shard)
        - shard_new_skill: Whether shard adds new skill (if has_shard)
    """
    if not REFERENCE_DATA.get('aghs_desc'):
        return {"error": "Aghanim's descriptions not loaded"}

    # aghs_desc is an array, find the hero by hero_id
    for hero_aghs in REFERENCE_DATA['aghs_desc']:
        if hero_aghs.get('hero_id') == hero_id:
            logger.info(f"Found Aghanim's details for hero ID {hero_id}")
            return hero_aghs

    logger.error(f"No Aghanim's details found for hero ID {hero_id}")
    return {"error": f"No Aghanim's details found for hero ID {hero_id}"}

def extract_match_sections(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract match sections as a dictionary.

    Use this in MCP tools to split large match data into manageable sections.

    Args:
        data: Match data dictionary (can be raw API response or JSON-RPC wrapped)

    Returns:
        Dictionary with section names as keys and their data as values

    Raises:
        ValueError: If match data structure is invalid or missing required fields
        TypeError: If data is not a dictionary

    Example:
        >>> from opendota_mcp.split_parsed_match import extract_match_sections
        >>> response = await fetch_api("/matches/12345")
        >>> sections = extract_match_sections(response)
        >>> players = sections['players']
        >>> teamfights = sections['teamfights']
        >>> metadata = sections['metadata']
    """
    # Handle JSON-RPC wrapper (if present)
    try:
        if 'result' in data and 'structuredContent' in data.get('result', {}):
            match = data['result']['structuredContent']
            logger.info("Extracted match from JSON-RPC result wrapper")
        elif 'structuredContent' in data:
            match = data['structuredContent']
            logger.info("Extracted match from structuredContent")
        elif 'match_id' in data and 'players' in data:
            match = data
            logger.info("Using data directly as match")
        else:
            logger.error(f"Could not find match data. Keys: {list(data.keys())}")
            raise ValueError(
                f"Could not find match data in JSON. Top-level keys: {list(data.keys())}"
            )
    except (KeyError, AttributeError) as e:
        logger.error(f"Data structure error: {e}")
        raise ValueError(f"Invalid data structure: {e}")

    # Validate match data
    if not isinstance(match, dict):
        logger.error(f"Match data is not a dictionary: {type(match).__name__}")
        raise ValueError(f"Match data must be a dictionary, got {type(match).__name__}")

    # Extract sections into a dictionary
    sections = {}

    section_keys = [
        'players', 'teamfights', 'objectives', 'chat', 'picks_bans',
        'radiant_gold_adv', 'radiant_xp_adv', 'cosmetics', 'od_data',
        'all_word_counts', 'my_word_counts'
    ]

    for section in section_keys:
        if section in match:
            sections[section] = match[section]

    logger.info(f"Extracted {len(sections)} sections: {list(sections.keys())}")

    # Add metadata (all scalar values)
    try:
        metadata = {k: v for k, v in match.items()
                    if not isinstance(v, (list, dict)) or k in ['all_word_counts', 'my_word_counts']}
        sections['metadata'] = metadata
        logger.info(f"Extracted metadata with {len(metadata)} fields")
    except AttributeError as e:
        logger.error(f"Failed to extract metadata: {e}")
        raise ValueError(f"Failed to extract metadata: {e}")

    return sections

def get_lane_role_by_id_logic(lane_role: int) -> Dict[str, Any]:
    """
    Get lane description by lane_role ID.
    
    Args:
        lane_role: Lane role ID (1-4)
    
    Returns:
        Dictionary with lane_role ID and description
    
    Raises:
        ValueError: If lane_role is not between 1-4
    
    Examples:
        - get_lane_role_by_id_logic(1) returns "Safe Lane (Carry-Position 1/Hard Support-Position 5)"
        - get_lane_role_by_id_logic(2) returns "Mid Lane (Position 2)"
        - get_lane_role_by_id_logic(3) returns "Off Lane (Offlane-Position 3/Soft Support-Position 4)"
        - get_lane_role_by_id_logic(4) returns "Jungle/Roaming (Position 4)"
    """
    if not isinstance(lane_role, int):
        raise ValueError(f"lane_role must be an integer, got {type(lane_role).__name__}")
    
    if lane_role not in LANE_DESCRIPTIONS:
        raise ValueError(
            f"Invalid lane_role: {lane_role}. Valid values are 1-4"
        )
    
    logger.info(f"Retrieved lane description for ID {lane_role}: {LANE_DESCRIPTIONS[lane_role]}")

    return {
        "lane_role": lane_role,
        "lane_role_name": LANE_DESCRIPTIONS[lane_role]
    }

async def process_player_items(player: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process player item data into a structured format.

    Extracts:
    - Final build (6 main items)
    - Neutral item
    - Key item timings (items > 2000 gold cost)

    Args:
        player: Player object from match response

    Returns:
        Dictionary with:
        - final_build: List of item names (6 items, null if empty slot)
        - neutral: Neutral item name or null
        - key_timings: List of {item, time, time_formatted} for major items
    """
    def format_time(seconds: int) -> str:
        """Format seconds to MM:SS"""
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}:{secs:02d}"

    def get_item_cost(item_name: str) -> int:
        """Get item cost from items.json"""
        if REFERENCE_DATA.get('items') and item_name in REFERENCE_DATA['items']:
            return REFERENCE_DATA['items'][item_name].get('cost', 0)
        return 0

    # Extract final build (item_0 through item_5)
    final_build = []
    for i in range(6):
        item_id = player.get(f"item_{i}", 0)
        try:
            if item_id and item_id != 0:
                item_name = await get_item_display_name_by_id(item_id)
                final_build.append(item_name)
            else:
                final_build.append(None)
        except Exception as e:
            logger.error(f"Failed to resolve item {item_id}: {e}")
            final_build.append(None)

    # Extract neutral item
    neutral_item_id = player.get("item_neutral", 0)
    neutral_item = None
    if neutral_item_id and neutral_item_id != 0:
        neutral_item = await get_item_display_name_by_id(neutral_item_id)

    # Extract key item timings (items with cost >= 2000 gold)
    key_timings = []
    purchase_log = player.get("purchase_log", [])

    for purchase in purchase_log:
        item_name = purchase.get("key")
        time = purchase.get("time")

        if item_name and time is not None:
            cost = get_item_cost(item_name)

            # Only include items >= 2000 gold and positive time (exclude pre-game)
            if cost >= 2000 and time >= 0:
                key_timings.append({
                    "item": item_name,
                    "time_formatted": format_time(time)
                })

    return {
        "final_build": final_build,
        "neutral": neutral_item,
        "key_timings": key_timings
    }

async def build_player_list(players: List[Dict[str, Any]], benchmark_fields: List[str]) -> List[Dict[str, Any]]:
    """
    Build structured player list with item data and benchmarks for match details.

    Args:
        players: List of player dictionaries from match data
        benchmark_fields: List of benchmark field names to include

    Returns:
        List of structured player dictionaries with:
        - Basic info (account_id, hero_name, team, etc.)
        - Performance stats (kills, deaths, assists, GPM, XPM, etc.)
        - Item data (final build, neutral item, key timings)
        - Benchmarks (percentiles for specified fields)
    """
    result = []
    for p in players:
        # Process item data
        items_data = await process_player_items(p)

        player_dict = {
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
            "damage_taken": sum(p.get("damage_taken", {}).values()),
            "teamfight_participation": p.get("teamfight_participation"),
            "observer_placed": p.get("obs_placed"),
            "sentry_placed": p.get("sen_placed"),
            "stuns": p.get("stuns"),
            "last_hits": p.get("last_hits"),
            "denies": p.get("denies"),
            "items": items_data,
            "benchmarks": {
                field: {
                    "raw": p.get("benchmarks", {}).get(field, {}).get("raw"),
                    "pct": (p.get("benchmarks", {}).get(field, {}).get("pct") or 0) * 100
                }
                for field in benchmark_fields
            }
        }
        result.append(player_dict)
    return result