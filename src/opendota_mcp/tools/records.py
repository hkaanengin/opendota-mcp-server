from datetime import UTC, datetime
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from opendota_mcp.api import OpenDotaClient
from opendota_mcp.api.types import RECORD_FIELDS
from opendota_mcp.models import Record, RecordsResult
from opendota_mcp.models.formatting import mmss
from opendota_mcp.reference import Reference
from opendota_mcp.resolve import resolve_stat_field
from opendota_mcp.tools.annotations import READ_ONLY


def register_records_tools(mcp: FastMCP, api: OpenDotaClient, reference: Reference) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def get_records(
        field: Annotated[
            str,
            Field(
                description=(
                    "The stat, in everyday words or OpenDota's name: kills, deaths, assists, "
                    "gpm, xpm, last hits, denies, hero damage, tower damage, hero healing, "
                    "duration."
                )
            ),
        ],
    ) -> RecordsResult:
        """All-time best single-match performances in one stat, across all public matches.

        Use for "highest GPM ever", "most kills in a game", "longest game ever".
        """
        stat = resolve_stat_field(field, RECORD_FIELDS)
        entries = await api.get_records(stat)
        return RecordsResult(
            stat=stat,
            records=[
                Record(
                    rank=rank,
                    value=entry.score,
                    value_mmss=mmss(entry.score) if stat == "duration" else None,
                    hero=reference.hero_name(entry.hero_id),
                    match_id=entry.match_id,
                    played_on=datetime.fromtimestamp(entry.start_time, tz=UTC).date(),
                )
                for rank, entry in enumerate(entries, start=1)
            ],
        )
