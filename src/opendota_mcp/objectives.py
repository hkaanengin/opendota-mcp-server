"""Objective processing: a Parsed match's raw objectives → readable events.

Ported from v1's `ObjectiveProcessor`. Covers first blood, towers, barracks and the
Ancient, Roshan (with the Aegis pickup folded in), Tormentors and courier kills; any other
objective still comes through, as an `other` event.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from opendota_mcp.api.types import MatchPlayerEntry, ObjectiveEntry
from opendota_mcp.models.formatting import mmss
from opendota_mcp.models.matches import EventType, MatchEvent, Side
from opendota_mcp.reference import Reference

logger = logging.getLogger(__name__)

RADIANT_SLOTS = 128
"""Player slots below this are on Radiant."""
RADIANT_TEAM = 2
"""How objectives name Radiant in `team`; Dire is 3."""
AEGIS_WINDOW = 30
"""Seconds after a Roshan kill within which an Aegis pickup is that kill's Aegis."""
KEY_MOMENT_TYPES = frozenset({"first_blood", "roshan", "barracks", "ancient"})
"""Always key moments. Of the towers only the first is; couriers and Tormentors never are."""

LANES = {"_top": "top", "_mid": "middle", "_bot": "bottom"}


def side_of_slot(player_slot: int) -> Side:
    return "Radiant" if player_slot < RADIANT_SLOTS else "Dire"


def other_side(side: Side) -> Side:
    return "Dire" if side == "Radiant" else "Radiant"


@dataclass(frozen=True)
class _Credit:
    """Who an event is credited to: a hero on a side, a side's creeps, or just a side."""

    side: Side
    hero: str | None = None
    creeps: bool = False

    def __str__(self) -> str:
        if self.hero:
            return f"{self.hero} ({self.side})"
        return f"{self.side} creeps" if self.creeps else self.side


def match_events(
    objectives: Sequence[ObjectiveEntry],
    players: Sequence[MatchPlayerEntry],
    reference: Reference,
) -> list[MatchEvent]:
    """Every objective as an event, in time order."""
    return _Processor(players, reference).process(objectives)


def key_moments(events: Sequence[MatchEvent]) -> list[MatchEvent]:
    """The few events that tell the story: first blood, the first tower, every Roshan,
    barracks and the Ancient."""
    first_tower = next((event for event in events if event.type == "tower"), None)
    return [e for e in events if e.type in KEY_MOMENT_TYPES or e is first_tower]


class _Processor:
    def __init__(self, players: Sequence[MatchPlayerEntry], reference: Reference) -> None:
        self._reference = reference
        self._heroes = {p.player_slot: reference.hero_name(p.hero_id) for p in players}
        self._handlers: dict[str, Callable[[ObjectiveEntry], MatchEvent]] = {
            "CHAT_MESSAGE_FIRSTBLOOD": self._first_blood,
            "CHAT_MESSAGE_COURIER_LOST": self._courier,
            "building_kill": self._building,
            "CHAT_MESSAGE_MINIBOSS_KILL": self._tormentor,
            "CHAT_MESSAGE_ROSHAN_KILL": self._roshan,
            "CHAT_MESSAGE_AEGIS": self._aegis,
        }

    def process(self, objectives: Sequence[ObjectiveEntry]) -> list[MatchEvent]:
        events: list[MatchEvent] = []
        # Index in `events` of the latest Roshan kill still waiting for its Aegis.
        roshan: int | None = None
        # An Aegis logged in the same second as its Roshan kill still sorts after it.
        in_order = sorted(objectives, key=lambda o: (o.time, o.type == "CHAT_MESSAGE_AEGIS"))
        for objective in in_order:
            event = self._handlers.get(objective.type, self._other)(objective)
            if event.type == "aegis" and event.hero and roshan is not None:
                kill = events[roshan]
                if event.time - kill.time <= AEGIS_WINDOW:
                    events[roshan] = kill.model_copy(
                        update={"description": f"{kill.description} (Aegis: {event.hero})"}
                    )
                    roshan = None
                    continue
            roshan = len(events) if event.type == "roshan" else roshan
            events.append(event)
        return events

    def _credit_slot(self, player_slot: int | None, *, team: int | None = None) -> _Credit | None:
        if player_slot is not None and player_slot >= 0:
            return _Credit(side_of_slot(player_slot), self._heroes.get(player_slot))
        if team is not None:
            return _Credit(_team_side(team))
        return None

    def _first_blood(self, objective: ObjectiveEntry) -> MatchEvent:
        credit = self._credit_slot(objective.player_slot)
        return _event(objective, "first_blood", credit, f"{_name(credit)} drew first blood")

    def _courier(self, objective: ObjectiveEntry) -> MatchEvent:
        loser = _team_side(objective.team)
        killer = self._credit_slot(objective.killer)
        if killer is None:
            credit = _Credit(other_side(loser))
            return _event(objective, "courier", credit, f"The {loser} courier was killed")
        return _event(objective, "courier", killer, f"{killer} killed the {loser} courier")

    def _building(self, objective: ObjectiveEntry) -> MatchEvent:
        key = str(objective.key or "")
        owner: Side = "Radiant" if "goodguys" in key else "Dire"
        credit = self._credit_slot(objective.player_slot) or self._credit_unit(
            objective.unit or "", other_side(owner)
        )
        lane = next((name for suffix, name in LANES.items() if key.endswith(suffix)), None)
        where = f"{lane} " if lane else ""
        if "fort" in key:
            return _event(
                objective,
                "ancient",
                _Credit(credit.side),
                f"{credit.side} destroyed the {owner} Ancient",
            )
        if "tower" in key:
            tier = key.split("tower")[1][:1]
            target = f"{where}T{tier} tower"
            kind: EventType = "tower"
        elif "rax" in key:
            target = f"{where}{'melee' if 'melee' in key else 'ranged'} barracks"
            kind = "barracks"
        else:
            return _event(objective, "other", credit, f"{credit} destroyed a {owner} building")
        return _event(objective, kind, credit, f"{credit} destroyed the {owner} {target}")

    def _credit_unit(self, unit: str, default: Side) -> _Credit:
        """Credit for a unit name such as `npc_dota_hero_jakiro` or `npc_dota_goodguys_siege`."""
        side: Side = "Radiant" if "goodguys" in unit else "Dire" if "badguys" in unit else default
        hero = self._reference.hero_name_for_unit(unit)
        if hero is not None:
            slot = next((s for s, name in self._heroes.items() if name == hero), None)
            return _Credit(side_of_slot(slot) if slot is not None else default, hero)
        return _Credit(side, creeps="creep" in unit or "siege" in unit)

    def _tormentor(self, objective: ObjectiveEntry) -> MatchEvent:
        credit = self._credit_slot(objective.player_slot, team=objective.team)
        return _event(objective, "tormentor", credit, f"{_name(credit)} killed a Tormentor")

    def _roshan(self, objective: ObjectiveEntry) -> MatchEvent:
        credit = _Credit(_team_side(objective.team))
        return _event(objective, "roshan", credit, f"{credit} killed Roshan")

    def _aegis(self, objective: ObjectiveEntry) -> MatchEvent:
        credit = self._credit_slot(objective.player_slot)
        return _event(objective, "aegis", credit, f"{_name(credit)} took the Aegis")

    def _other(self, objective: ObjectiveEntry) -> MatchEvent:
        logger.debug("Unhandled objective type %s: %r", objective.type, objective)
        what = objective.type.removeprefix("CHAT_MESSAGE_").replace("_", " ").lower()
        credit = self._credit_slot(objective.player_slot, team=objective.team)
        description = f"{what.capitalize()}: {credit}" if credit else what.capitalize()
        return _event(objective, "other", credit, description)


def _team_side(team: int | None) -> Side:
    return "Radiant" if team == RADIANT_TEAM else "Dire"


def _name(credit: _Credit | None) -> str:
    return str(credit) if credit else "Someone"


def _event(
    objective: ObjectiveEntry, kind: EventType, credit: _Credit | None, description: str
) -> MatchEvent:
    return MatchEvent(
        time=objective.time,
        time_mmss=mmss(objective.time),
        type=kind,
        side=credit.side if credit else None,
        hero=credit.hero if credit else None,
        description=description,
    )
