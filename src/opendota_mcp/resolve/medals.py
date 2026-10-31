"""The eight Dota medals: one table for formatting a Player's Rank tier and naming Rank brackets."""

from fastmcp.exceptions import ToolError

MEDALS = ("Herald", "Guardian", "Crusader", "Archon", "Legend", "Ancient", "Divine", "Immortal")
"""Medal names in order; a medal's number (1 Herald … 8 Immortal) is its index + 1."""
IMMORTAL = len(MEDALS)
MAX_STARS = 5
UNRANKED = "Unranked"


def medal_name(medal: int) -> str:
    """1 → "Herald" … 8 → "Immortal". Raises `ValueError` outside 1-8."""
    if not 1 <= medal <= len(MEDALS):
        raise ValueError(f"medal must be 1-{len(MEDALS)}, got {medal}")
    return MEDALS[medal - 1]


def format_rank_tier(rank_tier: int | None, leaderboard_rank: int | None = None) -> str:
    """74 → "Divine 4", 70 → "Divine", 80 with leaderboard rank 412 → "Immortal #412".

    Missing or impossible values (uncalibrated players, a 76 with six stars, an Immortal
    with stars such as 87) are `UNRANKED` rather than a made-up medal.
    """
    if rank_tier is None:
        return UNRANKED
    medal, stars = divmod(rank_tier, 10)
    if medal == IMMORTAL and stars == 0:
        return f"Immortal #{leaderboard_rank}" if leaderboard_rank else "Immortal"
    if not 1 <= medal < IMMORTAL or stars > MAX_STARS:
        return UNRANKED
    return f"{medal_name(medal)} {stars}" if stars else medal_name(medal)


def resolve_rank_bracket(value: str | int) -> int:
    """A medal name ("divine") or number (1-8, also as text) → OpenDota's Rank bracket number."""
    wanted = str(value).strip().lower()
    for medal, name in enumerate(MEDALS, start=1):
        if wanted in (name.lower(), str(medal)):
            return medal
    valid = ", ".join(f"{medal} {name}" for medal, name in enumerate(MEDALS, start=1))
    raise ToolError(
        f"Unknown rank bracket {value!r}. Use a medal name or its number: {valid}. "
        "Leave it out for all brackets combined."
    )
