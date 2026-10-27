from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from opendota_mcp.api.types import ParseState

Side = Literal["Radiant", "Dire"]
MatchSection = Literal["teamfights", "objectives", "chat", "advantage_graphs", "player_timings"]
EventType = Literal[
    "first_blood",
    "tower",
    "barracks",
    "ancient",
    "roshan",
    "aegis",
    "tormentor",
    "courier",
    "other",
]


class MatchEvent(BaseModel):
    time: int = Field(description="Seconds from the horn.")
    time_mmss: str
    type: EventType
    side: Side | None = Field(description="The side that made it happen or gained from it.")
    hero: str | None = Field(description="The hero credited, when one was.")
    description: str = Field(description='e.g. "Dire killed Roshan (Aegis: Kez)".')


class MatchDraft(BaseModel):
    radiant_picks: list[str] = Field(description="Hero names, in pick order.")
    radiant_bans: list[str]
    dire_picks: list[str]
    dire_bans: list[str]


class MatchPlayer(BaseModel):
    persona_name: str | None = Field(description="Display name; null for anonymous players.")
    account_id: int | None = Field(description="Null for anonymous players.")
    hero: str
    side: Side
    kills: int
    deaths: int
    assists: int
    net_worth: int | None
    level: int | None
    gold_per_min: int | None
    xp_per_min: int | None
    last_hits: int | None
    denies: int | None
    items: list[str] = Field(description="Final inventory; empty slots left out.")
    backpack: list[str] = Field(description="Final backpack; empty slots left out.")
    neutral_item: str | None


class MatchResult(BaseModel):
    match_id: int
    winner: Side | None = Field(description="Null for a match with no result.")
    radiant_score: int | None = Field(description="Radiant's hero kills.")
    dire_score: int | None = Field(description="Dire's hero kills.")
    duration: int = Field(description="Match length in seconds.")
    duration_mmss: str = Field(description='Match length as "MM:SS".')
    start_time: datetime = Field(description="When the match started, UTC.")
    game_mode: str = Field(description='e.g. "All Pick", "Turbo".')
    lobby_type: str = Field(description='e.g. "Ranked", "Unranked".')
    patch: str | None = Field(description='e.g. "7.39".')
    region: str | None
    draft: MatchDraft
    players: list[MatchPlayer] = Field(description="Radiant's five, then Dire's.")
    key_moments: list[MatchEvent] = Field(
        description="First blood, first tower, Roshan kills, barracks and the Ancient, in "
        "order. Empty for an unparsed match."
    )
    parsed: bool = Field(
        description="Whether the replay is parsed, so get_match_section has detail to give."
    )
    parse_note: str | None = Field(description="What to do when the match isn't parsed.")


class TeamfightParticipant(BaseModel):
    hero: str
    side: Side
    kills: list[str] = Field(description="Heroes this one killed in the fight.")
    deaths: int
    damage: int
    healing: int
    gold_change: int
    xp_change: int
    buybacks: int


class Teamfight(BaseModel):
    start: int = Field(description="Seconds from the horn.")
    start_mmss: str
    end: int
    end_mmss: str
    deaths: int
    radiant_gold_change: int = Field(description="Gold Radiant's heroes gained (or lost) in it.")
    dire_gold_change: int
    participants: list[TeamfightParticipant] = Field(
        description="Heroes that dealt damage, healed, killed or died in the fight."
    )


class ChatMessage(BaseModel):
    time: int = Field(description="Seconds from the horn; negative before it.")
    time_mmss: str
    persona_name: str | None
    hero: str | None
    side: Side | None
    message: str


class MatchChat(BaseModel):
    messages: list[ChatMessage] = Field(description="Typed chat, in order.")
    chat_wheel_lines: int = Field(description="Chat wheel lines used, which aren't listed.")


class AdvantagePoint(BaseModel):
    minute: int
    radiant_gold_lead: int = Field(description="Negative when Dire is ahead.")
    radiant_xp_lead: int = Field(description="Negative when Dire is ahead.")


class TimingCheckpoint(BaseModel):
    minute: int
    gold: int = Field(description="Total gold earned so far.")
    xp: int = Field(description="Total experience so far.")
    last_hits: int
    denies: int


class ItemTiming(BaseModel):
    item: str
    time: int = Field(description="Seconds from the horn.")
    time_mmss: str


class PlayerTimings(BaseModel):
    hero: str
    side: Side
    persona_name: str | None
    checkpoints: list[TimingCheckpoint] = Field(
        description="Every 5 minutes, plus the last minute."
    )
    key_items: list[ItemTiming] = Field(
        description="When each item costing 2000 gold or more was bought."
    )


class MatchSectionResult(BaseModel):
    match_id: int
    section: MatchSection
    teamfights: list[Teamfight] | None = Field(description="Set for the teamfights section.")
    objectives: list[MatchEvent] | None = Field(
        description="Set for the objectives section: every first blood, building, Roshan, "
        "Tormentor and courier event, in order."
    )
    chat: MatchChat | None = Field(description="Set for the chat section.")
    advantage_graphs: list[AdvantagePoint] | None = Field(
        description="Set for the advantage_graphs section: Radiant's lead each minute."
    )
    player_timings: list[PlayerTimings] | None = Field(
        description="Set for the player_timings section, one per player."
    )


ParseStatus = ParseState


class ParseRequestResult(BaseModel):
    match_id: int
    job_id: int = Field(description="OpenDota's parse job; pass it to get_match_parse_status.")
    message: str = Field(description="What happens next.")


class ParseStatusResult(BaseModel):
    match_id: int
    status: ParseStatus = Field(
        description="queued: waiting for a parser. parsing: being parsed now. parsed: detail "
        "is ready. failed: the parse ended without data (usually the replay is no longer "
        "available) or the job ID is unknown. not_requested: unparsed, no parse request known."
    )
    job_id: int | None = Field(description="The parse job checked, if one was known.")
    message: str = Field(description="What it means and what to do next.")
