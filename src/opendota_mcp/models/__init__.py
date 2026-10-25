"""Typed tool outputs. Every tool returns one of these, so FastMCP publishes an output schema."""

from opendota_mcp.models.heroes import (
    AghanimsUpgrade,
    HeroAttributes,
    HeroResult,
    HeroStats,
    PrimaryAttribute,
)
from opendota_mcp.models.items import ItemAbility, ItemResult
from opendota_mcp.models.records import Record, RecordsResult

__all__ = [
    "AghanimsUpgrade",
    "HeroAttributes",
    "HeroResult",
    "HeroStats",
    "ItemAbility",
    "ItemResult",
    "PrimaryAttribute",
    "Record",
    "RecordsResult",
]
