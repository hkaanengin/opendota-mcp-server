"""Parameter descriptions shared by every tool that takes the same kind of input."""

HERO = (
    'The hero: its name ("Anti-Mage"), a community nickname ("AM", "magina"), its '
    "OpenDota hero ID, or a close spelling."
)
ITEM = (
    'The item: its name ("Black King Bar"), a community nickname ("bkb", "aghs shard"), '
    "its OpenDota item ID, or a close spelling."
)
PLAYER = (
    "The player: their Account ID (the Friend ID shown in the Dota client), a player alias "
    "configured on this server, or their exact current Steam display name. Prefer the ID "
    "once known; an ambiguous name fails with candidates to choose from."
)
FILTERS = (
    "Optional: narrow which of the player's matches are counted. Turbo is left out unless "
    'game_mode is "turbo". The response says what was counted; relay its notes.'
)
MATCH_ID = "The match ID, e.g. from get_player_matches or the Dota client."
