"""The only code that talks to OpenDota.

Callers use one typed operation per endpoint and never build URLs. Responses are
validated into the `api` types here, so a changed OpenDota payload fails loudly at
the boundary rather than deep inside a tool.

Every call is paced by the rate limiter, and successful responses are cached for as
long as their kind of data stays fresh. Cache hits skip the limiter entirely.
"""

import logging
import math
from collections.abc import Callable, Hashable, Mapping
from typing import Any, TypeVar

import httpx
from fastmcp.exceptions import ToolError
from pydantic import SecretStr, TypeAdapter, ValidationError

from opendota_mcp.api.cache import (
    HERO_WIDE_TTL,
    PARSED_MATCH_TTL,
    PLAYER_TTL,
    UNPARSED_MATCH_TTL,
    ResponseCache,
)
from opendota_mcp.api.ratelimit import RateLimiter, seconds_until_next_window
from opendota_mcp.api.types import (
    AGHS_DESC,
    BENCHMARKS,
    HERO_ITEM_POPULARITY,
    HERO_LORE,
    HERO_MATCHUPS,
    HERO_STATS,
    HEROES,
    HISTOGRAM,
    ITEMS,
    MATCH,
    PARSE_JOB,
    PARSE_REQUEST,
    PATCHES,
    PLAYER,
    PLAYER_COUNTS,
    PLAYER_HEROES,
    PLAYER_MATCH_COLUMNS,
    PLAYER_MATCHES,
    PLAYER_PEERS,
    PLAYER_TOTALS,
    RATINGS,
    SEARCH,
    WIN_LOSS,
    AghsDescConstant,
    BenchmarkRole,
    HeroBenchmarks,
    HeroConstant,
    HeroItemPopularity,
    HeroMatchupEntry,
    HeroStatsEntry,
    HistogramEntry,
    ItemConstant,
    MatchResponse,
    ParseProgress,
    PatchConstant,
    PlayerCounts,
    PlayerHeroEntry,
    PlayerMatchEntry,
    PlayerPeerEntry,
    PlayerResponse,
    PlayerTotalEntry,
    RatingEntry,
    RecordEntry,
    SearchResult,
    WinLoss,
)
from opendota_mcp.clock import Clock

logger = logging.getLogger(__name__)

BASE_URL = "https://api.opendota.com/api"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)
PARSE_REQUEST_COST = 10
"""OpenDota counts a parse request as 10 calls against the rate limit."""
MAX_RETRY_WAIT = 60.0
"""Longest `Retry-After` worth waiting out inside a tool call; beyond it, fail at once."""

T = TypeVar("T")
Params = Mapping[str, str | int | tuple[int, ...] | tuple[str, ...]]
"""OpenDota query parameters; a tuple repeats the key. Part of the cache key, so filtered
queries never collide."""

_records = TypeAdapter(list[RecordEntry])
_MISSING = object()


class UnexpectedResponseError(Exception):
    """OpenDota answered with a payload that doesn't match its documented shape.

    Deliberately not a pydantic `ValidationError`: FastMCP reports those as the
    caller's invalid arguments, which would send the model chasing the wrong fix.
    """


def _parse(adapter: TypeAdapter[T], path: str, payload: Any) -> T:
    try:
        return adapter.validate_python(payload)
    except ValidationError as exc:
        raise UnexpectedResponseError(f"Unexpected OpenDota response for {path}: {exc}") from None


class PlayerNotFoundError(Exception):
    """OpenDota has no Player with this Account ID."""

    def __init__(self, account_id: int) -> None:
        super().__init__(f"no player with account ID {account_id}")
        self.account_id = account_id


class MatchNotFoundError(Exception):
    """OpenDota has no Match with this ID."""

    def __init__(self, match_id: int) -> None:
        super().__init__(f"no match with ID {match_id}")
        self.match_id = match_id


class _ApiKeyTransport(httpx.AsyncBaseTransport):
    """Adds `?api_key=` on the way out.

    Only the copy handed to the wire carries the key. The request httpx logs and attaches
    to `HTTPStatusError` is the caller's original, so the key can't leak into logs or errors.
    """

    def __init__(self, inner: httpx.AsyncBaseTransport, api_key: SecretStr) -> None:
        self._inner = inner
        self._api_key = api_key

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        keyed = httpx.Request(
            request.method,
            request.url.copy_merge_params({"api_key": self._api_key.get_secret_value()}),
            headers=request.headers,
            stream=request.stream,
            extensions=request.extensions,
        )
        return await self._inner.handle_async_request(keyed)

    async def aclose(self) -> None:
        await self._inner.aclose()


class OpenDotaClient:
    def __init__(
        self,
        *,
        api_key: SecretStr | None,
        rate_limit_rpm: int,
        transport: httpx.AsyncBaseTransport | None,
        clock: Clock,
    ) -> None:
        self._api_key = api_key
        self._transport = transport
        self._clock = clock
        self._limiter = RateLimiter(rate_limit_rpm, clock)
        self._cache = ResponseCache(clock)
        self._parse_jobs: dict[int, int] = {}
        self._http: httpx.AsyncClient | None = None

    async def get_records(self, field: str) -> list[RecordEntry]:
        """Top all-time performances in a record stat (see `RECORD_FIELDS`)."""
        return await self._get(f"/records/{field}", _records, ttl=HERO_WIDE_TTL)

    async def get_hero_stats(self) -> list[HeroStatsEntry]:
        """Every hero's public picks and wins per Rank bracket, plus Pro match picks and bans."""
        return await self._get("/heroStats", HERO_STATS, ttl=HERO_WIDE_TTL)

    async def get_hero_matchups(self, hero_id: int) -> list[HeroMatchupEntry]:
        """The hero's Pro match results against each opponent hero."""
        return await self._get(f"/heroes/{hero_id}/matchups", HERO_MATCHUPS, ttl=HERO_WIDE_TTL)

    async def get_hero_item_popularity(self, hero_id: int) -> HeroItemPopularity:
        """Items bought on the hero in Pro matches, per game phase."""
        return await self._get(
            f"/heroes/{hero_id}/itemPopularity", HERO_ITEM_POPULARITY, ttl=HERO_WIDE_TTL
        )

    async def get_hero_benchmarks(
        self, hero_id: int, bracket: int | None = None, role: BenchmarkRole | None = None
    ) -> HeroBenchmarks:
        """Stat percentiles over the hero's public games, optionally for one Rank bracket
        (1-8) and one role (`core` or `support`)."""
        params: dict[str, int | str] = {"hero_id": hero_id}
        if bracket is not None:
            params["bracket"] = bracket
        if role is not None:
            params["role"] = role
        return await self._get("/benchmarks", BENCHMARKS, ttl=HERO_WIDE_TTL, params=params)

    async def search_players(self, name: str) -> list[SearchResult]:
        """Players whose Persona name contains `name`. Fewer than 3 characters finds nothing."""
        return await self._get("/search", SEARCH, ttl=PLAYER_TTL, params={"q": name})

    async def get_player(self, account_id: int) -> PlayerResponse:
        """Profile and Rank tier. Raises `PlayerNotFoundError` for an unknown Account ID."""
        try:
            return await self._get(f"/players/{account_id}", PLAYER, ttl=PLAYER_TTL)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != httpx.codes.NOT_FOUND:
                raise
            raise PlayerNotFoundError(account_id) from None

    async def get_player_win_loss(self, account_id: int, filters: Params | None = None) -> WinLoss:
        """Wins and losses over the Player's games, narrowed by player filter `filters`."""
        return await self._get(
            f"/players/{account_id}/wl", WIN_LOSS, ttl=PLAYER_TTL, params=filters
        )

    async def get_player_heroes(
        self, account_id: int, filters: Params | None = None
    ) -> list[PlayerHeroEntry]:
        """Games and wins on every hero, including heroes never played (0 games)."""
        return await self._get(
            f"/players/{account_id}/heroes", PLAYER_HEROES, ttl=PLAYER_TTL, params=filters
        )

    async def get_player_peers(
        self, account_id: int, filters: Params | None = None
    ) -> list[PlayerPeerEntry]:
        """Players who shared the Player's matches, on either team."""
        return await self._get(
            f"/players/{account_id}/peers", PLAYER_PEERS, ttl=PLAYER_TTL, params=filters
        )

    async def get_player_totals(
        self, account_id: int, filters: Params | None = None
    ) -> list[PlayerTotalEntry]:
        """Each stat in `PLAYER_STAT_FIELDS` summed over the Player's games."""
        return await self._get(
            f"/players/{account_id}/totals", PLAYER_TOTALS, ttl=PLAYER_TTL, params=filters
        )

    async def get_player_histogram(
        self, account_id: int, field: str, filters: Params | None = None
    ) -> list[HistogramEntry]:
        """How a stat in `PLAYER_STAT_FIELDS` is spread over the Player's games, low to high."""
        return await self._get(
            f"/players/{account_id}/histograms/{field}", HISTOGRAM, ttl=PLAYER_TTL, params=filters
        )

    async def get_player_counts(
        self, account_id: int, filters: Params | None = None
    ) -> PlayerCounts:
        """Games and wins by game mode, lobby type, lane, region and patch."""
        return await self._get(
            f"/players/{account_id}/counts", PLAYER_COUNTS, ttl=PLAYER_TTL, params=filters
        )

    async def get_player_matches(
        self, account_id: int, filters: Params | None = None
    ) -> list[PlayerMatchEntry]:
        """The Player's matches, newest first. Without a `limit` filter, their whole history."""
        params = {**(filters or {}), "project": PLAYER_MATCH_COLUMNS}
        return await self._get(
            f"/players/{account_id}/matches", PLAYER_MATCHES, ttl=PLAYER_TTL, params=params
        )

    async def get_player_ratings(self, account_id: int) -> list[RatingEntry]:
        """Each change of the Player's Rank tier that OpenDota recorded."""
        return await self._get(f"/players/{account_id}/ratings", RATINGS, ttl=PLAYER_TTL)

    async def get_match(self, match_id: int, *, recheck_unparsed: bool = False) -> MatchResponse:
        """A finished Match. Raises `MatchNotFoundError` for an unknown match ID.

        A Parsed match never changes, so it stays cached; an unparsed one may be parsed at
        any time, so it's kept only briefly. `recheck_unparsed` refetches a cached unparsed
        copy, and the fresh one replaces it.
        """
        reuse = (lambda match: match.parsed) if recheck_unparsed else None
        try:
            return await self._get(f"/matches/{match_id}", MATCH, ttl=_match_ttl, reuse=reuse)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != httpx.codes.NOT_FOUND:
                raise
            raise MatchNotFoundError(match_id) from None

    async def request_parse(self, match_id: int) -> int:
        """Queue a parse of the Match's replay and return the job ID, without waiting.

        Raises `MatchNotFoundError` when OpenDota doesn't know the match.
        """
        path = f"/request/{match_id}"
        try:
            payload = await self._send_with_retry("POST", path, None, cost=PARSE_REQUEST_COST)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (httpx.codes.BAD_REQUEST, httpx.codes.NOT_FOUND):
                raise
            raise MatchNotFoundError(match_id) from None
        job_id = _parse(PARSE_REQUEST, path, payload).job.jobId
        self._parse_jobs[match_id] = job_id
        return job_id

    async def get_parse_progress(self, match_id: int, job_id: int | None = None) -> ParseProgress:
        """Where a parse of the Match stands. Raises `MatchNotFoundError` for an unknown match.

        Checks job `job_id`, else this session's latest request for the match. A job still
        in OpenDota's queue is `parsing` while a worker holds it (its next attempt is in the
        future) and `queued` otherwise; a job retrying after a failed attempt also reads as
        `parsing`. Once the job is gone, the match itself says whether it worked, and a
        cached unparsed copy is replaced by the fresh one.
        """
        if job_id is None:
            job_id = self._parse_jobs.get(match_id)
        if job_id is not None:
            job = await self._fetch(f"/request/{job_id}", PARSE_JOB)
            if job is not None:
                retry_at = job.next_attempt_time
                held = retry_at is not None and retry_at.timestamp() > self._clock.time()
                return ParseProgress(state="parsing" if held else "queued", job_id=job_id)
        match = await self.get_match(match_id, recheck_unparsed=True)
        if match.parsed:
            return ParseProgress(state="parsed", job_id=job_id)
        return ParseProgress(state="not_requested" if job_id is None else "failed", job_id=job_id)

    # Constants are not response-cached: the reference store keeps them and decides when
    # to refresh, and the items payload alone would crowd the cache.

    async def get_hero_constants(self) -> dict[str, HeroConstant]:
        """`/constants/heroes`, keyed by hero ID as a string."""
        return await self._fetch("/constants/heroes", HEROES)

    async def get_item_constants(self) -> dict[str, ItemConstant]:
        """`/constants/items`, keyed by internal item name."""
        return await self._fetch("/constants/items", ITEMS)

    async def get_aghs_desc_constants(self) -> list[AghsDescConstant]:
        return await self._fetch("/constants/aghs_desc", AGHS_DESC)

    async def get_hero_lore_constants(self) -> dict[str, str]:
        """`/constants/hero_lore`, keyed by hero internal name."""
        return await self._fetch("/constants/hero_lore", HERO_LORE)

    async def get_patch_constants(self) -> list[PatchConstant]:
        return await self._fetch("/constants/patch", PATCHES)

    async def aclose(self) -> None:
        """Close the connection pool. The next request opens a fresh one."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _get(
        self,
        path: str,
        adapter: TypeAdapter[T],
        *,
        ttl: float | Callable[[T], float | None] | None,
        params: Params | None = None,
        reuse: Callable[[T], bool] | None = None,
    ) -> T:
        """Fetch, validate and cache a GET response. Only valid responses are cached.

        `ttl` is seconds to keep it (`None`: until evicted), or a function of the response
        when how long it stays fresh depends on what came back. A cached response `reuse`
        rejects is fetched again.
        """
        key: Hashable = ("GET", path, tuple(sorted((params or {}).items())))
        cached = self._cache.get(key, _MISSING)
        if cached is not _MISSING and (reuse is None or reuse(cached)):
            logger.debug("GET %s (cached)", path)
            return cached  # type: ignore[no-any-return]
        value = await self._fetch(path, adapter, params)
        self._cache.put(key, value, ttl(value) if callable(ttl) else ttl)
        return value

    async def _fetch(self, path: str, adapter: TypeAdapter[T], params: Params | None = None) -> T:
        """Fetch and validate a GET response, bypassing the cache."""
        return _parse(adapter, path, await self._send_with_retry("GET", path, params))

    async def _send_with_retry(
        self, method: str, path: str, params: Params | None, *, cost: int = 1
    ) -> Any:
        """A 429 is retried once after `Retry-After`; OpenDota outages become `ToolError`."""
        for attempt in range(2):
            response = await self._send_once(method, path, params, cost)
            if response.status_code != httpx.codes.TOO_MANY_REQUESTS:
                break
            wait = _retry_after(response, self._clock.time())
            if attempt > 0 or wait > MAX_RETRY_WAIT:
                raise _rate_limited(wait)
            logger.info("OpenDota answered 429 for %s; retrying in %.1fs", path, wait)
            await self._clock.sleep(wait)
        if response.is_server_error:
            logger.warning("OpenDota answered %d for %s", response.status_code, path)
            raise ToolError(
                f"OpenDota is having problems (HTTP {response.status_code}). "
                "Try again in a few minutes."
            )
        response.raise_for_status()
        return response.json()

    async def _send_once(
        self, method: str, path: str, params: Params | None, cost: int
    ) -> httpx.Response:
        """One request, paced by the rate limiter."""
        await self._limiter.acquire(cost)
        logger.debug("%s %s", method, path)
        try:
            return await self._client().request(method, path, params=params)
        except httpx.TransportError as exc:
            logger.warning("OpenDota unreachable for %s: %s", path, type(exc).__name__)
            raise ToolError("OpenDota didn't respond. Try again in a few minutes.") from None

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            transport = self._transport
            if self._api_key is not None:
                transport = _ApiKeyTransport(transport or httpx.AsyncHTTPTransport(), self._api_key)
            self._http = httpx.AsyncClient(base_url=BASE_URL, transport=transport, timeout=TIMEOUT)
        return self._http


def _match_ttl(match: MatchResponse) -> float | None:
    return PARSED_MATCH_TTL if match.parsed else UNPARSED_MATCH_TTL


def _retry_after(response: httpx.Response, now: float) -> float:
    """Seconds OpenDota asked us to wait, or until its minute window resets if it didn't say."""
    try:
        return max(0.0, float(response.headers["Retry-After"]))
    except (KeyError, ValueError):
        return seconds_until_next_window(now)


def _rate_limited(wait: float) -> ToolError:
    when = f"{math.ceil(wait)}s" if wait < 120 else f"{math.ceil(wait / 60)} min"
    return ToolError(f"OpenDota rate limit hit, try again in {when}.")
