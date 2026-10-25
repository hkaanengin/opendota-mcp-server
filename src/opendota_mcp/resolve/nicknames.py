"""The curated Nickname tables shipped in `nicknames/`, one TOML file per kind."""

import re
import tomllib
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Literal


def normalize(text: str) -> str:
    """How names are compared, ignoring case, spaces and punctuation: "Anti-Mage" → "antimage"."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


@dataclass(frozen=True)
class NicknameTable:
    targets: dict[str, str]
    """Normalized nickname → internal name."""
    ambiguous: dict[str, tuple[str, ...]]
    """Normalized nickname the community uses for several targets → their internal names."""


@cache
def nickname_table(kind: Literal["heroes", "items"]) -> NicknameTable:
    data = tomllib.loads((files(__package__) / "nicknames" / f"{kind}.toml").read_text("utf-8"))
    ambiguous = data.pop("ambiguous", {})
    return NicknameTable(
        targets={normalize(nick): target for target, nicks in data.items() for nick in nicks},
        ambiguous={normalize(nick): tuple(targets) for nick, targets in ambiguous.items()},
    )
