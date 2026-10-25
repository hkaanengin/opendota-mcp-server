"""Typed tool outputs. Every tool returns one of these, so FastMCP publishes an output schema."""

from opendota_mcp.models.filters import FilterDisclosure
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
    PlayerWinLossResult,
    ResolvedPlayer,
)
from opendota_mcp.models.records import Record, RecordsResult

__all__ = [
    "AghanimsUpgrade",
    "FilterDisclosure",
    "FindPlayerResult",
    "HeroAttributes",
    "HeroResult",
    "HeroStats",
    "ItemAbility",
    "ItemResult",
    "PlayerCandidate",
    "PlayerHero",
    "PlayerProfileResult",
    "PlayerWinLossResult",
    "PrimaryAttribute",
    "Record",
    "RecordsResult",
    "ResolvedPlayer",
]
