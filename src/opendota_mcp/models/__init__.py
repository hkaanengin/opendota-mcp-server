"""Typed tool outputs. Every tool returns one of these, so FastMCP publishes an output schema."""

from opendota_mcp.models.records import Record, RecordsResult

__all__ = ["Record", "RecordsResult"]
