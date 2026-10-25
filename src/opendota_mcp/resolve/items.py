"""Item names, IDs, Nicknames and misspellings → an item's internal name."""

from opendota_mcp.reference import Reference
from opendota_mcp.resolve.names import resolve_name
from opendota_mcp.resolve.nicknames import nickname_table, normalize


def resolve_item(text: str | int, reference: Reference) -> str:
    """By exact name or ID, then the item Nickname table, then spelling.

    Items without a display name are internal-only and never match. Where several items
    share a display name (Dagon levels), the shortest internal name, the base item, wins.
    """
    named = {key: item for key, item in reference.items.items() if item.dname}
    base_first = sorted(named, key=lambda key: (len(key), key))
    names: dict[str, str] = {}
    for key in base_first:
        names.setdefault(normalize(key), key)
        names.setdefault(str(named[key].id), key)
    for key in base_first:
        names.setdefault(normalize(named[key].dname or ""), key)
    return resolve_name(
        text,
        kind="item",
        names=names,
        nicknames=nickname_table("items"),
        display={key: item.dname or key for key, item in named.items()},
    )
