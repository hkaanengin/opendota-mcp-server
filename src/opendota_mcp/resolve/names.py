"""Name resolution shared by heroes and items: exact name or ID, Nickname, then spelling."""

import difflib
from collections.abc import Mapping
from typing import TypeVar

from fastmcp.exceptions import ToolError

from opendota_mcp.resolve.nicknames import NicknameTable, normalize

K = TypeVar("K")

FUZZY_CUTOFF = 0.8
"""Similarity a misspelling needs to resolve on its own, e.g. "rubik" → Rubick (0.91)."""
SUGGESTION_CUTOFF = 0.6
"""Similarity a name needs to be offered as a "Did you mean" suggestion."""
MAX_SUGGESTIONS = 3


def resolve_name(
    text: str | int,
    *,
    kind: str,
    names: Mapping[str, K],
    nicknames: NicknameTable,
    display: Mapping[K, str],
) -> K:
    """Resolve `text` to a key of `display`.

    `names` maps every normalized exact name (display name, internal name, ID) to its key;
    the Nickname table's targets are internal names, so they resolve through `names` too.
    Raises a `ToolError` listing candidates when ambiguous, or suggestions when unmatched.
    """
    wanted = normalize(str(text))
    if wanted in names:
        return names[wanted]
    # A target missing from the live data (renamed upstream) is skipped, not an error.
    by_nickname = {
        nick: names[normalize(target)]
        for nick, target in nicknames.targets.items()
        if normalize(target) in names
    }
    if wanted in by_nickname:
        return by_nickname[wanted]
    candidates = [
        names[normalize(target)]
        for target in nicknames.ambiguous.get(wanted, ())
        if normalize(target) in names
    ]
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        raise _ambiguous(text, kind, [display[key] for key in candidates])

    # IDs are exact or nothing: "9999" is not a misspelling of hero 99.
    spellings = {
        spelling: key
        for spelling, key in {**by_nickname, **names}.items()
        if not spelling.isdigit()
    }
    scored = [] if wanted.isdigit() else _closest(wanted, spellings, cutoff=SUGGESTION_CUTOFF)
    if scored and scored[0][0] >= FUZZY_CUTOFF:
        best = [key for score, key in scored if score == scored[0][0]]
        if len(best) == 1:
            return best[0]
        raise _ambiguous(text, kind, [display[key] for key in best])

    message = f"No {kind} matches {str(text)!r}."
    suggestions = [display[key] for _, key in scored[:MAX_SUGGESTIONS]]
    if suggestions:
        message += f" Did you mean {_or(suggestions)}?"
    else:
        message += f" Use the {kind}'s name as shown in game."
    raise ToolError(message)


def _closest(wanted: str, spellings: Mapping[str, K], *, cutoff: float) -> list[tuple[float, K]]:
    """Distinct keys at least `cutoff` similar to `wanted`, best first, scored by their best."""
    if not wanted:
        return []
    best: dict[K, float] = {}
    matcher = difflib.SequenceMatcher(b=wanted)
    for spelling, key in spellings.items():
        matcher.set_seq1(spelling)
        if matcher.real_quick_ratio() < cutoff or matcher.quick_ratio() < cutoff:
            continue
        score = matcher.ratio()
        if score >= cutoff and score > best.get(key, 0.0):
            best[key] = score
    return sorted(((score, key) for key, score in best.items()), key=lambda pair: -pair[0])


def _ambiguous(text: str | int, kind: str, candidates: list[str]) -> ToolError:
    return ToolError(
        f"{str(text)!r} could mean {_or(candidates)}. "
        f"Ask which {kind} was meant, then call again with its full name."
    )


def _or(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} or {names[-1]}"
