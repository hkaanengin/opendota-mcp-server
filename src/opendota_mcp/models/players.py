from datetime import date

from pydantic import BaseModel, Field

from opendota_mcp.models.filters import FilterDisclosure


class ResolvedPlayer(BaseModel):
    """Who the answer is for. Included in every player tool's output."""

    account_id: int = Field(description="The Player's Account ID (Friend ID in the Dota client).")
    persona_name: str | None = Field(description="Their current display name.")


class PlayerHero(BaseModel):
    hero: str
    games: int
    wins: int
    win_rate: float | None = Field(description="Percent of games won; null with no games.")


class PlayerProfileResult(BaseModel):
    resolved_player: ResolvedPlayer
    rank: str = Field(description='Current medal, e.g. "Divine 4", "Immortal #412", or "Unranked".')
    wins: int
    losses: int
    win_rate: float | None = Field(description="Percent of games won; null with no games.")
    top_heroes: list[PlayerHero] = Field(description="Up to 10 most-played heroes, most first.")


class PlayerCandidate(BaseModel):
    persona_name: str | None
    account_id: int
    exact_name_match: bool = Field(description="True when the name matches exactly, ignoring case.")
    avatar: str | None = Field(description="Steam avatar image URL.")
    last_match_date: date | None = Field(description="UTC date of their latest match.")
    rank: str = Field(description='Current medal, e.g. "Divine 4", or "Unranked".')
    profile_url: str = Field(description="Their OpenDota profile page.")


class FindPlayerResult(BaseModel):
    players_found: int = Field(description="How many players OpenDota matched (at most 50).")
    candidates: list[PlayerCandidate] = Field(
        description="The closest names first, then the most recently active."
    )


class PlayerWinLossResult(BaseModel):
    resolved_player: ResolvedPlayer
    wins: int
    losses: int
    win_rate: float | None = Field(description="Percent of games won; null with no games.")
    filters: FilterDisclosure


class PlayerHeroesResult(BaseModel):
    resolved_player: ResolvedPlayer
    heroes: list[PlayerHero] = Field(description="Most-played first.")
    filters: FilterDisclosure


class PlayerPeer(BaseModel):
    persona_name: str | None = Field(description="Their current display name.")
    account_id: int
    games: int = Field(description="Matches played together on the same team.")
    wins: int = Field(description="Of those, how many were won.")
    win_rate: float | None = Field(description="Percent of games together won.")
    last_played_date: date | None = Field(description="UTC date of their latest match together.")


class PlayerPeersResult(BaseModel):
    resolved_player: ResolvedPlayer
    peers: list[PlayerPeer] = Field(description="Most games together first.")
    filters: FilterDisclosure


class PlayerTotal(BaseModel):
    field: str = Field(description="OpenDota's name for the stat, e.g. gold_per_min.")
    stat: str = Field(description="The stat in plain words.")
    games: int = Field(
        description="Games that record this stat; some are only known for Parsed matches."
    )
    total: int | float = Field(description="The stat summed over those games.")
    average: float | None = Field(description="Per game, to two decimals; null with no games.")
    average_mmss: str | None = Field(description="The average as MM:SS when the stat is duration.")


class PlayerTotalsResult(BaseModel):
    resolved_player: ResolvedPlayer
    totals: list[PlayerTotal]
    filters: FilterDisclosure


class HistogramBucket(BaseModel):
    low: int | float = Field(description="Games with the stat at least this...")
    high: int | float = Field(description="...and below this.")
    games: int
    wins: int
    win_rate: float | None = Field(description="Percent of games won; null with no games.")
    range_mmss: str | None = Field(description='The range as "MM:SS-MM:SS" for duration.')


class PlayerHistogramResult(BaseModel):
    resolved_player: ResolvedPlayer
    field: str = Field(description="OpenDota's name for the stat, e.g. gold_per_min.")
    stat: str = Field(description="The stat in plain words.")
    games: int = Field(description="Games counted across all buckets.")
    buckets: list[HistogramBucket] = Field(
        description="Equal-width ranges, low to high. Empty ranges at either end are left out."
    )
    filters: FilterDisclosure
