"""Shared test harness.

Every behaviour test drives the server the way a model would: build the app from
test `Settings`, connect FastMCP's in-memory client and call tools by name.
OpenDota is replayed from recorded responses under `tests/fixtures/opendota/`;
any request without a matching route fails, so no test can reach the network.
"""

import json
from collections.abc import AsyncIterator, Callable
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

SETTINGS_ENV_VARS = tuple(name.upper() for name in Settings.model_fields)


def load_fixture(name: str) -> Any:
    """A recorded OpenDota response, by path relative to `tests/fixtures/opendota/`."""
    return json.loads((FIXTURES / name).read_text())


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
    return respx.MockRouter(base_url=OPENDOTA_BASE_URL, assert_all_called=False)


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
