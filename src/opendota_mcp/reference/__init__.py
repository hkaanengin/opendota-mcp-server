"""Hero (and later item) reference data.

Callers look things up by ID and never know where the data came from. Today that
is the snapshot of OpenDota `/constants/heroes` bundled in `snapshots/`.
"""

import json
from importlib.resources import files
from typing import Any


class Reference:
    def __init__(self, heroes: dict[str, Any]) -> None:
        self._hero_names = {
            int(hero["id"]): str(hero["localized_name"]) for hero in heroes.values()
        }

    @classmethod
    def bundled(cls) -> "Reference":
        snapshots = files("opendota_mcp.reference") / "snapshots"
        return cls(heroes=json.loads((snapshots / "heroes.json").read_text(encoding="utf-8")))

    def hero_name(self, hero_id: int) -> str:
        """Display name, e.g. 1 → "Anti-Mage". Unknown IDs get a readable placeholder."""
        return self._hero_names.get(hero_id, f"Unknown hero (id {hero_id})")
