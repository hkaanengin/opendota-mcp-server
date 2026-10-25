"""Shared test harness.

Every behaviour test drives the server the way a model would: build the app from
test `Settings`, connect FastMCP's in-memory client and call tools by name.
OpenDota is replayed from recorded responses under `tests/fixtures/opendota/`;
any request without a matching route fails, so no test can reach the network.

The server fetches `/constants/*` when it starts. Those routes answer with the bundled
snapshots by default, and a test can override one by name, e.g.
`opendota.routes["constants/heroes"].respond(500)`.
"""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from importlib.resources import files
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastmcp import Client, FastMCP

from opendota_mcp.server import create_app
from opendota_mcp.settings import Settings

OPENDOTA_BASE_URL = "https://api.opendota.com/api"
FIXTURES = Path(__file__).parent / "fixtures" / "opendota"
SNAPSHOTS = files("opendota_mcp.reference") / "snapshots"
CONSTANTS = ("heroes", "items", "aghs_desc", "hero_lore", "patch")
"""The `/constants/{resource}` the server loads at startup."""

SETTINGS_ENV_VARS = tuple(name.upper() for name in Settings.model_fields)

API_KEY = "0b5bd1a3-6f4e-4b8a-9f7c-2d1e3c4b5a69"
"""A well-formed (UUID) OpenDota key for tests."""
RECORDS = [{"match_id": 1, "start_time": 1791134272, "hero_id": 1, "score": 30}]
"""A minimal valid `/records/{field}` response."""


def load_fixture(name: str) -> Any:
    """A recorded OpenDota response, by path relative to `tests/fixtures/opendota/`."""
    return json.loads((FIXTURES / name).read_text())


def bundled_constants(resource: str) -> Any:
    """The snapshot of `/constants/{resource}` shipped in the package."""
    return json.loads((SNAPSHOTS / f"{resource}.json").read_text(encoding="utf-8"))


def api_calls(opendota: respx.MockRouter) -> int:
    """Outbound OpenDota requests, not counting the `/constants/*` fetched at startup."""
    return sum(
        1 for call in opendota.calls if not call.request.url.path.startswith("/api/constants/")
    )


class FakeClock:
    """Stands in for wall time: `sleep` advances time instantly and records the wait."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's real environment and `.env` out of every test."""
    for var in SETTINGS_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    def make(**overrides: Any) -> Settings:
        return Settings(_env_file=None, **overrides)

    return make


@pytest.fixture
def opendota() -> respx.MockRouter:
    """Routes for recorded OpenDota responses, injected as the app's HTTP transport.

    Nothing is patched globally: the app only sees these routes because the factory
    takes the transport as a test hook. Unrouted requests raise.
    """
    router = respx.MockRouter(base_url=OPENDOTA_BASE_URL, assert_all_called=False)
    for resource in CONSTANTS:
        router.get(f"/constants/{resource}", name=f"constants/{resource}").respond(
            json=bundled_constants(resource)
        )
    return router


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def app(
    make_settings: Callable[..., Settings], opendota: respx.MockRouter, clock: FakeClock
) -> FastMCP:
    return create_app(
        make_settings(), transport=httpx.MockTransport(opendota.async_handler), clock=clock
    )


@pytest.fixture
async def client(app: FastMCP) -> AsyncIterator[Client[Any]]:
    async with Client(app) as client:
        yield client


Connect = Callable[..., AbstractAsyncContextManager[Client[Any]]]


@pytest.fixture
def connect(
    make_settings: Callable[..., Settings], opendota: respx.MockRouter, clock: FakeClock
) -> Connect:
    """Like `client`, but for an app built from custom settings, e.g. `connect(api_key=...)`."""

    @asynccontextmanager
    async def connect(**settings: Any) -> AsyncIterator[Client[Any]]:
        app = create_app(
            make_settings(**settings),
            transport=httpx.MockTransport(opendota.async_handler),
            clock=clock,
        )
        async with Client(app) as client:
            yield client

    return connect
