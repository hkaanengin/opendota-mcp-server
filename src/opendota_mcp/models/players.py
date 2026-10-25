from datetime import date

from pydantic import BaseModel, Field


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
