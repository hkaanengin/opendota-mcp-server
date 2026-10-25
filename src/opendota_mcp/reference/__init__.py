"""Hero and item reference data.

Callers ask the store for the current `Reference` and look things up by ID or internal
name. They never know whether the data came from OpenDota `/constants/*` or from the
snapshots bundled in `snapshots/`.
"""

from opendota_mcp.reference.data import Reference
from opendota_mcp.reference.store import ReferenceStore

__all__ = ["Reference", "ReferenceStore"]
