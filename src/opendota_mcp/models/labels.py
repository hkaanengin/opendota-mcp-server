"""Readable names for the game mode, lobby type and region IDs OpenDota reports."""

GAME_MODE_NAMES: dict[int, str] = {
    0: "Unknown",
    1: "All Pick (legacy)",
    2: "Captains Mode",
    3: "Random Draft",
    4: "Single Draft",
    5: "All Random",
    6: "Intro",
    7: "Diretide",
    8: "Reverse Captains Mode",
    9: "Greeviling",
    10: "Tutorial",
    11: "Mid Only",
    12: "Least Played",
    13: "Limited Heroes",
    14: "Compendium Matchmaking",
    15: "Custom",
    16: "Captains Draft",
    17: "Balanced Draft",
    18: "Ability Draft",
    19: "Event",
    20: "All Random Deathmatch",
    21: "1v1 Mid",
    # What the Dota client calls All Pick; OpenDota's "all draft".
    22: "All Pick",
    23: "Turbo",
    24: "Mutation",
    25: "Coaches Challenge",
}

LOBBY_TYPE_NAMES: dict[int, str] = {
    0: "Unranked",
    1: "Practice",
    2: "Tournament",
    3: "Tutorial",
    4: "Co-op with bots",
    5: "Ranked team (legacy)",
    6: "Ranked solo (legacy)",
    7: "Ranked",
    8: "1v1 Mid",
    9: "Battle Cup",
    10: "Local bots",
    11: "Spectator",
    12: "Event",
    13: "Gauntlet",
    14: "New player",
    15: "Featured",
}

REGION_NAMES: dict[int, str] = {
    1: "US West",
    2: "US East",
    3: "Europe",
    5: "Singapore",
    6: "Dubai",
    7: "Australia",
    8: "Stockholm",
    9: "Austria",
    10: "Brazil",
    11: "South Africa",
    12: "China (Telecom Shanghai)",
    13: "China (Unicom)",
    14: "Chile",
    15: "Peru",
    16: "India",
    17: "China (Telecom Guangdong)",
    18: "China (Telecom Zhejiang)",
    19: "Japan",
    20: "China (Telecom Wuhan)",
    25: "China (Unicom Tianjin)",
    37: "Taiwan",
    38: "Argentina",
}


def game_mode_name(game_mode: int) -> str:
    return GAME_MODE_NAMES.get(game_mode) or f"Game mode {game_mode}"


def lobby_type_name(lobby_type: int) -> str:
    return LOBBY_TYPE_NAMES.get(lobby_type) or f"Lobby type {lobby_type}"


def region_name(region: int) -> str:
    return REGION_NAMES.get(region) or f"Region {region}"
