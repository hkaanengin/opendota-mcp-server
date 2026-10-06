"""The only code that talks to OpenDota.

Callers use one typed operation per endpoint and never build URLs. Responses are
validated into the `api` types here, so a changed OpenDota payload fails loudly at
the boundary rather than deep inside a tool.
"""

import logging
from typing import Any, TypeVar

import httpx
from pydantic import TypeAdapter, ValidationError

from opendota_mcp.api.types import RecordEntry
from opendota_mcp.clock import Clock

logger = logging.getLogger(__name__)

BASE_URL = "https://api.opendota.com/api"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

T = TypeVar("T")

_records = TypeAdapter(list[RecordEntry])


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


class OpenDotaClient:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None, clock: Clock) -> None:
        self._transport = transport
        self._clock = clock  # paces requests once the rate limiter lands
        self._http: httpx.AsyncClient | None = None

    async def get_records(self, field: str) -> list[RecordEntry]:
        """Top all-time performances in a record stat (see `RECORD_FIELDS`)."""
        path = f"/records/{field}"
        return _parse(_records, path, await self._get(path))

    async def aclose(self) -> None:
        """Close the connection pool. The next request opens a fresh one."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _get(self, path: str) -> Any:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=BASE_URL, transport=self._transport, timeout=TIMEOUT
            )
        logger.debug("GET %s", path)
        response = await self._http.get(path)
        response.raise_for_status()
        return response.json()
