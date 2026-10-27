"""`get_match` summaries and `get_match_section` details, against recorded matches."""

from typing import Any

import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from opendota_mcp.api.cache import MAX_ENTRIES
from tests.conftest import FakeClock, api_calls, load_fixture

PARSED_ID = 8638411837
UNPARSED_ID = 9032502907
SECTIONS = ("teamfights", "objectives", "chat", "advantage_graphs", "player_timings")


@pytest.fixture
def parsed(opendota: respx.MockRouter) -> respx.Route:
    return opendota.get(f"/matches/{PARSED_ID}").respond(
        json=load_fixture(f"matches/{PARSED_ID}_parsed.json")
    )


@pytest.fixture
def unparsed(opendota: respx.MockRouter) -> respx.Route:
    return opendota.get(f"/matches/{UNPARSED_ID}").respond(
        json=load_fixture(f"matches/{UNPARSED_ID}_unparsed.json")
    )


async def get_match(client: Client[Any], match_id: int) -> dict[str, Any]:
    result = await client.call_tool("get_match", {"match_id": match_id})
    assert result.structured_content is not None
    return result.structured_content


async def get_section(client: Client[Any], match_id: int, section: str) -> dict[str, Any]:
    result = await client.call_tool("get_match_section", {"match_id": match_id, "section": section})
    assert result.structured_content is not None
    return result.structured_content


async def test_summary_gives_result_duration_mode_and_parse_status(
    client: Client[Any], parsed: respx.Route
) -> None:
    match = await get_match(client, PARSED_ID)

    assert match["match_id"] == PARSED_ID
    assert match["winner"] == "Radiant"
    assert (match["radiant_score"], match["dire_score"]) == (66, 44)
    assert (match["duration"], match["duration_mmss"]) == (3415, "56:55")
    assert match["game_mode"] == "All Pick"
    assert match["lobby_type"] == "Unranked"
    assert match["parsed"] is True
    assert match["parse_note"] is None


async def test_summary_draft_uses_hero_names(client: Client[Any], parsed: respx.Route) -> None:
    draft = (await get_match(client, PARSED_ID))["draft"]

    assert draft["radiant_picks"] == ["Earth Spirit", "Elder Titan", "Spectre", "Riki", "Undying"]
    assert draft["dire_picks"] == ["Tusk", "Jakiro", "Timbersaw", "Kez", "Necrophos"]
    assert len(draft["radiant_bans"]) == 5
    assert draft["dire_bans"] == ["Shadow Fiend", "Phantom Lancer"]


async def test_summary_lists_each_player_with_kda_net_worth_and_items_by_name(
    client: Client[Any], parsed: respx.Route
) -> None:
    players = (await get_match(client, PARSED_ID))["players"]

    assert len(players) == 10
    assert [p["side"] for p in players] == ["Radiant"] * 5 + ["Dire"] * 5
    assert players[0] == {
        "persona_name": "xinobillie",
        "account_id": 36872251,
        "hero": "Riki",
        "side": "Radiant",
        "kills": 15,
        "deaths": 7,
        "assists": 22,
        "net_worth": 28516,
        "level": 29,
        "gold_per_min": 556,
        "xp_per_min": 1081,
        "last_hits": 302,
        "denies": 15,
        "items": [
            "Daedalus",
            "Disperser",
            "Skull Basher",
            "Aghanim's Scepter",
            "Manta Style",
            "Power Treads",
        ],
        "backpack": ["Bottle"],
        "neutral_item": "Rattlecage",
    }
    # Empty inventory slots are left out rather than shown as gaps.
    assert players[2]["hero"] == "Elder Titan"
    assert len(players[2]["items"]) == 5
    assert players[2]["backpack"] == []


async def test_summary_key_moments_read_as_events(client: Client[Any], parsed: respx.Route) -> None:
    moments = (await get_match(client, PARSED_ID))["key_moments"]

    assert moments[0] == {
        "time": 14,
        "time_mmss": "00:14",
        "type": "first_blood",
        "side": "Dire",
        "hero": "Necrophos",
        "description": "Necrophos (Dire) drew first blood",
    }
    described = [(m["time_mmss"], m["description"]) for m in moments]
    assert ("43:05", "Dire killed Roshan (Aegis: Timbersaw)") in described
    assert described[-1] == ("56:56", "Radiant destroyed the Dire Ancient")
    assert {m["type"] for m in moments} <= {"first_blood", "tower", "barracks", "roshan", "ancient"}
    # Key moments stay short: no courier kills, and only the first tower.
    assert [m["type"] for m in moments].count("tower") == 1
    assert len(moments) <= 12


async def test_unparsed_summary_says_so_and_points_to_a_parse_request(
    client: Client[Any], unparsed: respx.Route
) -> None:
    match = await get_match(client, UNPARSED_ID)

    assert match["parsed"] is False
    assert "request_match_parse" in match["parse_note"]
    assert match["key_moments"] == []
    assert match["winner"] == "Dire"
    assert match["lobby_type"] == "Ranked"
    assert match["players"][0]["hero"] == "Legion Commander"
    assert match["players"][0]["persona_name"] == "сырник"
    assert len(match["draft"]["radiant_picks"]) == 5


async def test_unknown_match_fails_with_a_next_step(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    opendota.get("/matches/123").respond(404, json={"error": "Not Found"})

    with pytest.raises(ToolError, match="No match with ID 123"):
        await client.call_tool("get_match", {"match_id": 123})


async def test_objectives_section_covers_every_kind_of_event(
    client: Client[Any], parsed: respx.Route
) -> None:
    section = await get_section(client, PARSED_ID, "objectives")

    events = section["objectives"]
    assert section["section"] == "objectives"
    assert {e["type"] for e in events} == {
        "first_blood",
        "courier",
        "tower",
        "barracks",
        "tormentor",
        "roshan",
        "ancient",
    }
    described = {(e["time_mmss"], e["description"]) for e in events}
    assert {
        ("02:54", "Timbersaw (Dire) killed the Radiant courier"),
        ("21:29", "Undying (Radiant) killed the Dire courier"),
        ("27:37", "The Radiant courier was killed"),
        ("09:44", "Jakiro (Dire) destroyed the Radiant bottom T1 tower"),
        ("18:51", "Dire creeps destroyed the Radiant top T1 tower"),
        ("33:56", "Spectre (Radiant) destroyed the Dire middle melee barracks"),
        ("51:56", "Radiant creeps destroyed the Dire T4 tower"),
        ("20:45", "Jakiro (Dire) killed a Tormentor"),
        ("52:53", "Dire killed Roshan (Aegis: Kez)"),
    } <= described
    # Each Aegis pickup is folded into the Roshan kill it came from.
    assert not any(e["type"] == "aegis" for e in events)
    assert all(e["side"] in ("Radiant", "Dire") for e in events)
    assert [e["time"] for e in events] == sorted(e["time"] for e in events)


async def test_teamfights_section_names_heroes_and_gold_swings(
    client: Client[Any], parsed: respx.Route
) -> None:
    fights = (await get_section(client, PARSED_ID, "teamfights"))["teamfights"]

    assert len(fights) == 18
    first = fights[0]
    assert (first["start_mmss"], first["end_mmss"], first["deaths"]) == ("04:19", "04:57", 4)
    riki = next(p for p in first["participants"] if p["hero"] == "Riki")
    assert riki == {
        "hero": "Riki",
        "side": "Radiant",
        "kills": ["Tusk"],
        "deaths": 0,
        "damage": 250,
        "healing": 220,
        "gold_change": 321,
        "xp_change": 488,
        "buybacks": 0,
    }
    raw = load_fixture(f"matches/{PARSED_ID}_parsed.json")["teamfights"][0]["players"]
    assert first["radiant_gold_change"] == sum(p["gold_delta"] for p in raw[:5])
    assert first["dire_gold_change"] == sum(p["gold_delta"] for p in raw[5:])


async def test_chat_section_gives_who_said_what_and_when(
    client: Client[Any], parsed: respx.Route
) -> None:
    chat = (await get_section(client, PARSED_ID, "chat"))["chat"]

    assert chat["chat_wheel_lines"] == 29
    assert len(chat["messages"]) == 40
    assert chat["messages"][0] == {
        "time": 1126,
        "time_mmss": "18:46",
        "persona_name": "PK | Imprint.gg",
        "hero": "Necrophos",
        "side": "Dire",
        "message": "hi ET",
    }


async def test_advantage_graphs_section_gives_radiant_leads_per_minute(
    client: Client[Any], parsed: respx.Route
) -> None:
    graphs = (await get_section(client, PARSED_ID, "advantage_graphs"))["advantage_graphs"]

    assert len(graphs) == 57
    assert graphs[1] == {
        "minute": 1,
        "radiant_gold_lead": -63,
        "radiant_xp_lead": -29,
    }


async def test_player_timings_section_gives_checkpoints_and_item_timings(
    client: Client[Any], parsed: respx.Route
) -> None:
    timings = (await get_section(client, PARSED_ID, "player_timings"))["player_timings"]

    assert len(timings) == 10
    riki = timings[0]
    assert riki["hero"] == "Riki"
    minutes = [c["minute"] for c in riki["checkpoints"]]
    assert minutes == [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 56]
    assert riki["checkpoints"][1]["gold"] > 0
    assert riki["key_items"], "Riki bought items costing 2000+"
    assert all(item["time"] >= 0 for item in riki["key_items"])
    assert "Daedalus" in {item["item"] for item in riki["key_items"]}


async def test_sections_not_asked_for_are_left_out(
    client: Client[Any], parsed: respx.Route
) -> None:
    section = await get_section(client, PARSED_ID, "chat")

    assert all(section[name] is None for name in SECTIONS if name != "chat")


@pytest.mark.parametrize("asked", ["Advantage Graphs", "player-timings", " CHAT "])
async def test_section_names_are_forgiving(
    client: Client[Any], parsed: respx.Route, asked: str
) -> None:
    section = await get_section(client, PARSED_ID, asked)

    assert section[section["section"]] is not None


async def test_invalid_section_fails_listing_the_valid_ones(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    with pytest.raises(ToolError) as error:
        await client.call_tool("get_match_section", {"match_id": PARSED_ID, "section": "wards"})

    for valid in SECTIONS:
        assert valid in str(error.value)
    assert api_calls(opendota) == 0


@pytest.mark.parametrize("section", SECTIONS)
async def test_sections_of_an_unparsed_match_fail_suggesting_a_parse_request(
    client: Client[Any], unparsed: respx.Route, section: str
) -> None:
    with pytest.raises(ToolError) as error:
        await client.call_tool("get_match_section", {"match_id": UNPARSED_ID, "section": section})

    message = str(error.value)
    assert "isn't parsed" in message
    assert "request_match_parse" in message


async def test_summary_and_several_sections_cost_one_request(
    client: Client[Any], parsed: respx.Route
) -> None:
    await get_match(client, PARSED_ID)
    for section in ("teamfights", "objectives", "chat"):
        await get_section(client, PARSED_ID, section)

    assert parsed.call_count == 1


async def test_a_parsed_match_stays_cached(
    client: Client[Any], parsed: respx.Route, clock: FakeClock
) -> None:
    await get_match(client, PARSED_ID)
    clock.advance(7 * 24 * 60 * 60)
    await get_match(client, PARSED_ID)

    assert parsed.call_count == 1


async def test_an_unparsed_match_is_cached_only_briefly(
    client: Client[Any], unparsed: respx.Route, clock: FakeClock
) -> None:
    await get_match(client, UNPARSED_ID)
    await get_match(client, UNPARSED_ID)
    assert unparsed.call_count == 1

    clock.advance(10 * 60)
    await get_match(client, UNPARSED_ID)
    assert unparsed.call_count == 2


async def test_least_recently_used_match_is_evicted_past_the_cap(
    client: Client[Any], opendota: respx.MockRouter
) -> None:
    template = load_fixture(f"matches/{UNPARSED_ID}_unparsed.json")
    small = {**template, "od_data": {**template["od_data"], "has_parsed": True}, "version": 22}

    def respond(request: Any, match_id: str) -> respx.MockResponse:
        return respx.MockResponse(200, json={**small, "match_id": int(match_id)})

    route = opendota.get(path__regex=r"/matches/(?P<match_id>\d+)").mock(side_effect=respond)

    await get_match(client, 1)
    await get_match(client, 2)
    for match_id in range(3, MAX_ENTRIES + 2):
        await get_match(client, match_id)
        if match_id == 3:
            await get_match(client, 1)  # 1 is now more recently used than 2
    assert route.call_count == MAX_ENTRIES + 1

    await get_match(client, 1)
    assert route.call_count == MAX_ENTRIES + 1
    await get_match(client, 2)
    assert route.call_count == MAX_ENTRIES + 2


async def test_match_tools_publish_output_schemas_and_are_read_only(
    client: Client[Any],
) -> None:
    tools = {tool.name: tool for tool in await client.list_tools()}

    for name in ("get_match", "get_match_section"):
        tool = tools[name]
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.output_schema is not None
    assert {"players", "draft", "key_moments", "parsed"} <= set(
        tools["get_match"].output_schema["properties"]  # type: ignore[index]
    )
    description = tools["get_match"].description or ""
    assert "get_match_section" in description
    assert "request_match_parse" in description
