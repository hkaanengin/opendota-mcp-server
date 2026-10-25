"""Lane and Position words → the Lane OpenDota filters by (its `lane_role`).

OpenDota records only where a hero laned, and only for Parsed matches. A Position maps to
the Lane it plays in, so pos 1/5 (safe lane) and pos 3/4 (off lane) can't be told apart.
"""

from dataclasses import dataclass

from fastmcp.exceptions import ToolError

from opendota_mcp.resolve.nicknames import normalize

LANE_NAMES = {1: "safe lane", 2: "mid lane", 3: "off lane", 4: "jungle"}
POSITION_LANES = {1: 1, 2: 2, 3: 3, 4: 3, 5: 1}
SHARED_LANE = {
    pos: other
    for pos, lane in POSITION_LANES.items()
    for other, other_lane in POSITION_LANES.items()
    if other != pos and other_lane == lane
}
"""Position → the other Position that plays the same Lane."""

LANE_WORDS = {
    1: ("safe lane", "safelane", "safe", "easy lane"),
    2: ("mid lane", "midlane", "mid", "middle"),
    3: ("off lane", "offlane", "off", "hard lane"),
    4: ("jungle", "jungler", "jungling"),
}
POSITION_WORDS = {
    1: ("carry", "hard carry", "safe laner", "safelaner"),
    2: ("midlaner", "mid laner", "solo mid"),
    3: ("offlaner", "off laner"),
    4: ("soft support", "roamer", "roaming support"),
    5: ("hard support", "full support"),
}
_LANES = {normalize(word): lane for lane, words in LANE_WORDS.items() for word in words}
_POSITIONS = {
    **{normalize(word): pos for pos, words in POSITION_WORDS.items() for word in words},
    **{
        normalize(f"{prefix}{pos}"): pos
        for pos in POSITION_LANES
        for prefix in ("", "pos ", "position ", "p")
    },
}


@dataclass(frozen=True)
class LaneFilter:
    lane_role: int
    label: str
    note: str
    """How the filter was applied, for the response's disclosure."""


def resolve_lane(value: str | int) -> LaneFilter:
    """A Lane word, or a Position (number 1-5, "pos 1", "carry", ...) mapped to its Lane."""
    wanted = normalize(str(value))
    if wanted in _LANES:
        lane = _LANES[wanted]
        return LaneFilter(lane, LANE_NAMES[lane], f"Filtered by {LANE_NAMES[lane]}.")
    if wanted in _POSITIONS:
        return _position(_POSITIONS[wanted])
    if wanted == "support":
        raise ToolError(
            "'support' could be pos 4 (off lane) or pos 5 (safe lane). Ask which, then call "
            'again with "pos 4" or "pos 5".'
        )
    raise ToolError(
        f"Unknown lane {value!r}. Use a lane (safe lane, mid lane, off lane, jungle) or a "
        "position (pos 1 to pos 5, carry, soft support, hard support)."
    )


def _position(pos: int) -> LaneFilter:
    lane = POSITION_LANES[pos]
    note = f"Filtered by {LANE_NAMES[lane]}, where pos {pos} plays."
    if pos in SHARED_LANE:
        first, second = sorted((pos, SHARED_LANE[pos]))
        note += (
            f" OpenDota doesn't record positions, so pos {first} and pos {second} can't be "
            "told apart."
        )
    return LaneFilter(lane, f"{LANE_NAMES[lane]} (pos {pos})", note)
