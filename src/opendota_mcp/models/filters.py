from pydantic import BaseModel, Field


class FilterDisclosure(BaseModel):
    """What a filtered answer covered. Included in every filtered player tool's output."""

    applied: list[str] = Field(description="Each filter as applied, in plain words.")
    game_modes: str = Field(description="Which games were counted; Turbo is left out unless asked.")
    lane_note: str | None = Field(
        description="How the lane filter was applied, e.g. a Position mapped to its Lane."
    )
    parsed_only_note: str | None = Field(
        description="Set when lane-filtered: only Parsed matches can be counted."
    )
