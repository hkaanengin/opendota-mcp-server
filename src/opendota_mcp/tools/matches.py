from typing import Annotated, get_args

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from opendota_mcp.api import MatchNotFoundError, OpenDotaClient
from opendota_mcp.api.types import ChatEntry, MatchPlayerEntry, MatchResponse, TeamfightEntry
from opendota_mcp.models import (
    AdvantagePoint,
    ChatMessage,
    ItemTiming,
    MatchChat,
    MatchDraft,
    MatchPlayer,
    MatchResult,
    MatchSection,
    MatchSectionResult,
    ParseRequestResult,
    ParseStatus,
    ParseStatusResult,
    PlayerTimings,
    Side,
    Teamfight,
    TeamfightParticipant,
    TimingCheckpoint,
)
from opendota_mcp.models.formatting import mmss, utc_datetime
from opendota_mcp.models.labels import game_mode_name, lobby_type_name, region_name
from opendota_mcp.objectives import key_moments, match_events, side_of_slot
from opendota_mcp.reference import Reference, ReferenceStore
from opendota_mcp.tools.annotations import READ_ONLY, WRITES
from opendota_mcp.tools.descriptions import MATCH_ID

SECTIONS: tuple[MatchSection, ...] = get_args(MatchSection)
KEY_ITEM_COST = 2000
"""Items at least this expensive are a player's key timings."""
CHECKPOINT_MINUTES = 5
UNPARSED_NOTE = (
    "This match isn't parsed, so teamfights, objectives, chat, graphs and timings aren't "
    "available. Offer to request a parse with request_match_parse; it takes a few minutes."
)
PARSE_MESSAGES: dict[ParseStatus, str] = {
    "queued": "Waiting for a parser; check again in a few minutes.",
    "parsing": "Being parsed now; check again in a minute or two.",
    "parsed": "Parsed. get_match and get_match_section now have the full detail.",
    "failed": (
        "The parse ended without producing data. Usually the replay is no longer available "
        "(Valve keeps replays only for a few weeks), so requesting it again rarely helps. "
        "If the job ID was passed in, check it belongs to this match."
    ),
    "not_requested": (
        "The match isn't parsed and no parse request is known for it. If one was made "
        "earlier, pass its job_id; otherwise request one with request_match_parse."
    ),
}


def register_match_tools(mcp: FastMCP, api: OpenDotaClient, references: ReferenceStore) -> None:
    async def fetch(match_id: int) -> tuple[MatchResponse, Reference]:
        try:
            match = await api.get_match(match_id)
        except MatchNotFoundError:
            raise _no_match(match_id) from None
        return match, await references.current()

    @mcp.tool(annotations=READ_ONLY)
    async def get_match(
        match_id: Annotated[int, Field(description=MATCH_ID)],
    ) -> MatchResult:
        """A compact summary of one match: winner, score, length, game mode, the draft, each
        player's hero, KDA, net worth and items, a few key moments, and whether the replay
        is parsed.

        Use for "who won match X", "how did I do in my last game", "what did the carry
        build". For more, call get_match_section (teamfights, objectives, chat,
        advantage_graphs, player_timings); it costs no extra OpenDota request. Those need a
        parsed match: if `parsed` is false, offer a parse with request_match_parse.
        """
        match, reference = await fetch(match_id)
        events = match_events(match.objectives or [], match.players, reference)
        return MatchResult(
            match_id=match.match_id,
            winner=None
            if match.radiant_win is None
            else "Radiant"
            if match.radiant_win
            else "Dire",
            radiant_score=match.radiant_score,
            dire_score=match.dire_score,
            duration=match.duration,
            duration_mmss=mmss(match.duration),
            start_time=utc_datetime(match.start_time),
            game_mode=game_mode_name(match.game_mode),
            lobby_type=lobby_type_name(match.lobby_type),
            patch=reference.patch_name(match.patch) if match.patch is not None else None,
            region=region_name(match.region) if match.region is not None else None,
            draft=_draft(match, reference),
            players=[_player(player, reference) for player in _in_order(match.players)],
            key_moments=key_moments(events),
            parsed=match.parsed,
            parse_note=None if match.parsed else UNPARSED_NOTE,
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_match_section(
        match_id: Annotated[int, Field(description=MATCH_ID)],
        section: Annotated[
            str,
            Field(
                description=(
                    "One of: teamfights (each fight's heroes, kills, damage and gold swing), "
                    "objectives (first blood, towers, barracks, Roshan, Tormentors, couriers), "
                    "chat, advantage_graphs (Radiant's gold and XP lead each minute), "
                    "player_timings (gold, XP and last hits every 5 minutes, key item times)."
                )
            ),
        ],
    ) -> MatchSectionResult:
        """One detailed part of a parsed match, after get_match gave the summary. Cached with
        the summary, so several sections cost a single OpenDota request.

        Use for "show the teamfights", "when did they take Roshan", "what did they say in
        chat", "when was Radiant ahead", "when did the carry get BKB".
        """
        wanted = _section(section)
        match, reference = await fetch(match_id)
        if not match.parsed:
            raise ToolError(
                f"Match {match_id} isn't parsed, so its {wanted.replace('_', ' ')} aren't "
                "available. Request a parse with request_match_parse, then try again in a "
                "few minutes."
            )
        players = _in_order(match.players)
        return MatchSectionResult(
            match_id=match.match_id,
            section=wanted,
            teamfights=(
                [_teamfight(fight, players, reference) for fight in match.teamfights or []]
                if wanted == "teamfights"
                else None
            ),
            objectives=(
                match_events(match.objectives or [], players, reference)
                if wanted == "objectives"
                else None
            ),
            chat=_chat(match.chat or [], players, reference) if wanted == "chat" else None,
            advantage_graphs=_advantage(match) if wanted == "advantage_graphs" else None,
            player_timings=(
                [_timings(player, reference) for player in players]
                if wanted == "player_timings"
                else None
            ),
        )

    @mcp.tool(annotations=WRITES)
    async def request_match_parse(
        match_id: Annotated[int, Field(description=MATCH_ID)],
    ) -> ParseRequestResult:
        """Ask OpenDota to parse a match's replay, so teamfights, objectives, chat, graphs
        and timings become available. Returns at once; the parse itself takes a few minutes.

        Use when get_match says the match isn't parsed and the user wants the detail. Then
        check progress with get_match_parse_status. Costs as much of the rate limit as 10
        ordinary calls, so don't repeat it while a parse is pending.
        """
        try:
            job_id = await api.request_parse(match_id)
        except MatchNotFoundError:
            raise _no_match(match_id) from None
        return ParseRequestResult(
            match_id=match_id,
            job_id=job_id,
            message=(
                "Parse requested. It usually takes a few minutes; check back with "
                "get_match_parse_status, then use get_match and get_match_section."
            ),
        )

    @mcp.tool(annotations=READ_ONLY)
    async def get_match_parse_status(
        match_id: Annotated[int, Field(description=MATCH_ID)],
        job_id: Annotated[
            int | None,
            Field(
                description="The job_id request_match_parse returned. Optional: this "
                "server remembers its own requests until it restarts."
            ),
        ] = None,
    ) -> ParseStatusResult:
        """Whether a requested parse is queued, parsing, parsed or failed.

        Use after request_match_parse, when the user asks "is it ready yet". Once parsed,
        get_match and get_match_section return the detailed data.
        """
        try:
            progress = await api.get_parse_progress(match_id, job_id)
        except MatchNotFoundError:
            raise _no_match(match_id) from None
        return ParseStatusResult(
            match_id=match_id,
            status=progress.state,
            job_id=progress.job_id,
            message=PARSE_MESSAGES[progress.state],
        )


def _no_match(match_id: int) -> ToolError:
    return ToolError(
        f"No match with ID {match_id} on OpenDota. Check the ID; a match that just "
        "ended can take a few minutes to appear."
    )


def _section(asked: str) -> MatchSection:
    normalized = "_".join(asked.strip().lower().replace("-", " ").split())
    for section in SECTIONS:
        if normalized == section:
            return section
    raise ToolError(f"Unknown match section {asked!r}. Choose one of: {', '.join(SECTIONS)}.")


def _in_order(players: list[MatchPlayerEntry]) -> list[MatchPlayerEntry]:
    """Radiant's five, then Dire's: the order teamfights list players in."""
    return sorted(players, key=lambda player: player.player_slot)


def _draft(match: MatchResponse, reference: Reference) -> MatchDraft:
    picks_bans = sorted(match.picks_bans or [], key=lambda entry: entry.order)

    def heroes(team: int, *, picks: bool) -> list[str]:
        return [
            reference.hero_name(entry.hero_id)
            for entry in picks_bans
            if entry.team == team and entry.is_pick == picks
        ]

    if not picks_bans:
        # Some modes record no draft; the picks are still the heroes played.
        played: dict[Side, list[str]] = {"Radiant": [], "Dire": []}
        for player in _in_order(match.players):
            played[side_of_slot(player.player_slot)].append(reference.hero_name(player.hero_id))
        return MatchDraft(
            radiant_picks=played["Radiant"],
            radiant_bans=[],
            dire_picks=played["Dire"],
            dire_bans=[],
        )
    return MatchDraft(
        radiant_picks=heroes(0, picks=True),
        radiant_bans=heroes(0, picks=False),
        dire_picks=heroes(1, picks=True),
        dire_bans=heroes(1, picks=False),
    )


def _items(item_ids: list[int | None], reference: Reference) -> list[str]:
    return [reference.item_name_by_id(item_id) for item_id in item_ids if item_id]


def _player(player: MatchPlayerEntry, reference: Reference) -> MatchPlayer:
    inventory = [getattr(player, f"item_{slot}") for slot in range(6)]
    backpack = [player.backpack_0, player.backpack_1, player.backpack_2]
    return MatchPlayer(
        persona_name=player.personaname,
        account_id=player.account_id,
        hero=reference.hero_name(player.hero_id),
        side=side_of_slot(player.player_slot),
        kills=player.kills,
        deaths=player.deaths,
        assists=player.assists,
        net_worth=player.net_worth,
        level=player.level,
        gold_per_min=player.gold_per_min,
        xp_per_min=player.xp_per_min,
        last_hits=player.last_hits,
        denies=player.denies,
        items=_items(inventory, reference),
        backpack=_items(backpack, reference),
        neutral_item=reference.item_name_by_id(player.item_neutral)
        if player.item_neutral
        else None,
    )


def _teamfight(
    fight: TeamfightEntry, players: list[MatchPlayerEntry], reference: Reference
) -> Teamfight:
    participants = []
    gold: dict[Side, int] = {"Radiant": 0, "Dire": 0}
    for player, entry in zip(players, fight.players, strict=False):
        gold[side_of_slot(player.player_slot)] += entry.gold_delta
        kills = [
            reference.hero_name_for_unit(unit) or unit
            for unit, count in entry.killed.items()
            if unit.startswith("npc_dota_hero_")
            for _ in range(count)
        ]
        if not (entry.damage or entry.healing or entry.deaths or kills):
            continue
        participants.append(
            TeamfightParticipant(
                hero=reference.hero_name(player.hero_id),
                side=side_of_slot(player.player_slot),
                kills=kills,
                deaths=entry.deaths,
                damage=entry.damage,
                healing=entry.healing,
                gold_change=entry.gold_delta,
                xp_change=entry.xp_delta,
                buybacks=entry.buybacks,
            )
        )
    return Teamfight(
        start=fight.start,
        start_mmss=mmss(fight.start),
        end=fight.end,
        end_mmss=mmss(fight.end),
        deaths=fight.deaths,
        radiant_gold_change=gold["Radiant"],
        dire_gold_change=gold["Dire"],
        participants=participants,
    )


def _chat(
    chat: list[ChatEntry], players: list[MatchPlayerEntry], reference: Reference
) -> MatchChat:
    by_slot = {player.player_slot: player for player in players}
    messages = []
    for line in chat:
        if line.type != "chat":
            continue
        player = by_slot.get(line.player_slot) if line.player_slot is not None else None
        messages.append(
            ChatMessage(
                time=line.time,
                time_mmss=mmss(line.time),
                persona_name=player.personaname if player else None,
                hero=reference.hero_name(player.hero_id) if player else None,
                side=side_of_slot(player.player_slot) if player else None,
                message=str(line.key),
            )
        )
    return MatchChat(
        messages=messages, chat_wheel_lines=sum(1 for line in chat if line.type == "chatwheel")
    )


def _advantage(match: MatchResponse) -> list[AdvantagePoint]:
    gold = match.radiant_gold_adv or []
    xp = match.radiant_xp_adv or []
    return [
        AdvantagePoint(minute=minute, radiant_gold_lead=gold_lead, radiant_xp_lead=xp_lead)
        for minute, (gold_lead, xp_lead) in enumerate(zip(gold, xp, strict=False))
    ]


def _timings(player: MatchPlayerEntry, reference: Reference) -> PlayerTimings:
    gold, xp = player.gold_t or [], player.xp_t or []
    last_hits, denies = player.lh_t or [], player.dn_t or []
    minutes = len(gold)
    checkpoints = list(range(0, minutes, CHECKPOINT_MINUTES))
    if minutes and checkpoints[-1] != minutes - 1:
        checkpoints.append(minutes - 1)

    def at(series: list[int], minute: int) -> int:
        return series[minute] if minute < len(series) else 0

    key_items = []
    for purchase in player.purchase_log or []:
        item = reference.items.get(purchase.key)
        if purchase.time >= 0 and item and (item.cost or 0) >= KEY_ITEM_COST:
            key_items.append(
                ItemTiming(
                    item=reference.item_name(purchase.key),
                    time=purchase.time,
                    time_mmss=mmss(purchase.time),
                )
            )
    return PlayerTimings(
        hero=reference.hero_name(player.hero_id),
        side=side_of_slot(player.player_slot),
        persona_name=player.personaname,
        checkpoints=[
            TimingCheckpoint(
                minute=minute,
                gold=at(gold, minute),
                xp=at(xp, minute),
                last_hits=at(last_hits, minute),
                denies=at(denies, minute),
            )
            for minute in checkpoints
        ],
        key_items=key_items,
    )
