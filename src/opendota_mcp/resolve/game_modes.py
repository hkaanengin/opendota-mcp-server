"""Game mode words ("ranked", "turbo", "all pick") → OpenDota's game mode / lobby type filters."""

from dataclasses import dataclass

from fastmcp.exceptions import ToolError

from opendota_mcp.resolve.nicknames import normalize

RANKED_LOBBY = 7


@dataclass(frozen=True)
class GameMode:
    label: str
    game_mode: int | None = None
    lobby_type: int | None = None
    standard: bool = True
    """Counted by OpenDota's default `significant=1`. Asking for a non-standard mode (such
    as Turbo) has to switch that off, or OpenDota would return no games at all."""


RANKED = GameMode("Ranked", lobby_type=RANKED_LOBBY)

_MODES = (
    (RANKED, ("ranked", "ranked matchmaking", "ranked mm")),
    (GameMode("Unranked", lobby_type=0), ("unranked", "normal", "normal matchmaking")),
    (GameMode("Battle Cup", lobby_type=9), ("battle cup",)),
    # Matchmaking All Pick is OpenDota's game mode 22 ("all draft"), not the legacy 1.
    (GameMode("All Pick", game_mode=22), ("all pick", "ap")),
    (GameMode("Captains Mode", game_mode=2), ("captains mode", "captain's mode", "cm")),
    (GameMode("Random Draft", game_mode=3), ("random draft", "rd")),
    (GameMode("Single Draft", game_mode=4), ("single draft", "sd")),
    (GameMode("All Random", game_mode=5), ("all random", "ar")),
    (GameMode("Captains Draft", game_mode=16), ("captains draft", "captain's draft")),
    (GameMode("Turbo", game_mode=23, standard=False), ("turbo",)),
    (GameMode("Ability Draft", game_mode=18, standard=False), ("ability draft",)),
    (
        GameMode("All Random Deathmatch", game_mode=20, standard=False),
        ("all random deathmatch", "ardm"),
    ),
    (GameMode("1v1 Mid", game_mode=21, standard=False), ("1v1 mid", "1v1", "1 v 1 mid")),
)
GAME_MODES = {normalize(word): mode for mode, words in _MODES for word in words}


def resolve_game_mode(text: str) -> tuple[GameMode, ...]:
    """One mode, or Ranked plus a mode for "ranked all pick" and the like."""
    wanted = normalize(text)
    mode = GAME_MODES.get(wanted)
    if mode is not None:
        return (mode,)
    ranked = normalize("ranked")
    mode = GAME_MODES.get(wanted.removeprefix(ranked)) if wanted.startswith(ranked) else None
    if mode is not None and mode.lobby_type is None:
        return (RANKED, mode)
    options = ", ".join(words[0] for _, words in _MODES)
    raise ToolError(f"Unknown game mode {text!r}. Use one of: {options}.")
