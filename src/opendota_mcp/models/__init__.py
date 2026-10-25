"""Typed tool outputs. Every tool returns one of these, so FastMCP publishes an output schema."""

from opendota_mcp.models.heroes import (
    AghanimsUpgrade,
    HeroAttributes,
    HeroResult,
    HeroStats,
    PrimaryAttribute,
)
from opendota_mcp.models.items import ItemAbility, ItemResult
from opendota_mcp.models.players import (
    FindPlayerResult,
    PlayerCandidate,
    PlayerHero,
    PlayerProfileResult,
    ResolvedPlayer,
)
from opendota_mcp.models.records import Record, RecordsResult

__all__ = [
    "AghanimsUpgrade",
    "FindPlayerResult",
    "HeroAttributes",
    "HeroResult",
    "HeroStats",
    "ItemAbility",
    "ItemResult",
    "PlayerCandidate",
    "PlayerHero",
    "PlayerProfileResult",
    "PrimaryAttribute",
    "Record",
    "RecordsResult",
    "ResolvedPlayer",
]
