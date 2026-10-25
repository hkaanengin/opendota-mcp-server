"""Patch versions ("7.39", "this patch") → OpenDota's patch index."""

import re
from collections.abc import Sequence

from fastmcp.exceptions import ToolError

from opendota_mcp.api.types import PatchConstant

CURRENT = {"this patch", "current patch", "current", "latest patch", "latest", "this"}
PREVIOUS = {"previous patch", "last patch", "previous"}
SHOWN_VERSIONS = 5
_VERSION = re.compile(r"(?:patch\s*)?v?(\d+\.\d+)[a-z]?")


def resolve_patch(value: str | float, patches: Sequence[PatchConstant]) -> PatchConstant:
    """By version, ignoring a letter suffix ("7.39c" is within 7.39), or relative to now.

    `patches` are oldest first. A float such as 7.4 reads as "7.40".
    """
    text = f"{value:.2f}" if isinstance(value, float) else re.sub(r"\s+", " ", value).strip()
    text = text.lower()
    if text in CURRENT and patches:
        return patches[-1]
    if text in PREVIOUS and len(patches) > 1:
        return patches[-2]
    if match := _VERSION.fullmatch(text):
        for patch in patches:
            if patch.name == match[1]:
                return patch
    recent = ", ".join(patch.name for patch in reversed(patches[-SHOWN_VERSIONS:]))
    raise ToolError(
        f'Unknown patch {value!r}. Use a version such as {recent}, or "this patch" or '
        '"previous patch".'
    )
