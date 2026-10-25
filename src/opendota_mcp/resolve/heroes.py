"""Hero names, IDs, Nicknames and misspellings → a hero."""

from opendota_mcp.api.types import HeroConstant
from opendota_mcp.reference import Reference
from opendota_mcp.resolve.names import resolve_name
from opendota_mcp.resolve.nicknames import nickname_table, normalize


def resolve_hero(text: str | int, reference: Reference) -> HeroConstant:
    """By exact name or ID, then the hero Nickname table, then spelling."""
    names: dict[str, int] = {}
    for hero in reference.heroes.values():
        for name in (str(hero.id), hero.localized_name, hero.internal_name):
            names.setdefault(normalize(name), hero.id)
    hero_id = resolve_name(
        text,
        kind="hero",
        names=names,
        nicknames=nickname_table("heroes"),
        display={hero.id: hero.localized_name for hero in reference.heroes.values()},
    )
    return reference.heroes[hero_id]
