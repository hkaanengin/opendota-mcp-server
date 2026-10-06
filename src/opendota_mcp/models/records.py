from datetime import date

from pydantic import BaseModel, Field


class Record(BaseModel):
    rank: int = Field(description="1 is the all-time best.")
    value: int | float = Field(description="The record value; seconds when the stat is duration.")
    value_mmss: str | None = Field(description="The value as MM:SS when the stat is duration.")
    hero: str
    match_id: int
    played_on: date = Field(description="UTC date the match was played.")


class RecordsResult(BaseModel):
    stat: str = Field(description="The OpenDota stat the records are for, e.g. gold_per_min.")
    records: list[Record]
