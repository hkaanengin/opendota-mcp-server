from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from opendota_mcp.api.types import ItemAttribConstant
from opendota_mcp.models import ItemAbility, ItemResult
from opendota_mcp.reference import ReferenceStore
from opendota_mcp.resolve import resolve_item
from opendota_mcp.tools.annotations import READ_ONLY
from opendota_mcp.tools.descriptions import ITEM


def register_item_tools(mcp: FastMCP, references: ReferenceStore) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def get_item(item: Annotated[str | int, Field(description=ITEM)]) -> ItemResult:
        """An item's facts: cost, stat bonuses, what its abilities do, cooldown, mana cost
        and what it's built from.

        Use for "how much is BKB", "what does Linken's do", "what's in a Skadi".
        """
        reference = await references.current()
        key = resolve_item(item, reference)
        found = reference.items[key]
        return ItemResult(
            id=found.id,
            name=found.dname or key,
            cost=found.cost,
            stats=[_stat(attrib) for attrib in found.attrib or [] if attrib.display],
            abilities=[
                ItemAbility(kind=ability.type, name=ability.title, description=ability.description)
                for ability in found.abilities or []
            ],
            cooldown=_number(found.cd),
            mana_cost=_number(found.mc),
            components=[reference.item_name(part) for part in found.components or []],
            notes=found.notes or None,
            lore=found.lore or None,
        )


def _stat(attrib: ItemAttribConstant) -> str:
    return (attrib.display or "").replace("{value}", attrib.value).strip()


def _number(value: int | float | bool | None) -> int | float | None:
    """OpenDota sends `false` for "none"; a zero cooldown or mana cost means none too."""
    if isinstance(value, bool) or not value:
        return None
    return value
