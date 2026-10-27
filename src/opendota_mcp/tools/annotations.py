from typing import Any

READ_ONLY: dict[str, Any] = {"readOnlyHint": True}
WRITES: dict[str, Any] = {"readOnlyHint": False, "destructiveHint": False}
"""Queues work on OpenDota, so not read-only, though nothing is lost by repeating it."""
