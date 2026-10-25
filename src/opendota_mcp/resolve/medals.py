"""The eight Dota medals: one table for formatting a Player's Rank tier and naming Rank brackets."""

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
