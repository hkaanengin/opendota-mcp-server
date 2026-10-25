"""App factory and console entry point."""

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP
from pydantic import ValidationError

from opendota_mcp import __version__
from opendota_mcp.api import OpenDotaClient
from opendota_mcp.clock import Clock, SystemClock
from opendota_mcp.reference import Reference
from opendota_mcp.settings import Settings
from opendota_mcp.tools import register_all_tools

logger = logging.getLogger(__name__)

INSTRUCTIONS = (
    "Answers questions about Dota 2 players, matches and heroes using OpenDota data. "
    "Tools accept everyday names (heroes, stats) and fail with a message saying what to do next."
)


def create_app(
    settings: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Clock | None = None,
) -> FastMCP:
    """Build the server. `transport` and `clock` are test hooks; production leaves them unset."""
    api = OpenDotaClient(
        api_key=settings.opendota_api_key,
        rate_limit_rpm=settings.rate_limit_rpm,
        transport=transport,
        clock=clock or SystemClock(),
    )

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await api.aclose()

    mcp = FastMCP(
        "OpenDota",
        instructions=INSTRUCTIONS,
        version=__version__,
        lifespan=lifespan,
        # Unexpected exceptions still come back as MCP errors (isError), but with a generic
        # message: internals such as request URLs never reach the model. ToolError messages
        # are written for the model and pass through unchanged.
        mask_error_details=True,
    )
    register_all_tools(mcp, api, Reference.bundled())
    return mcp


def main() -> None:
    try:
        settings = Settings()
    except ValidationError as exc:
        sys.exit(f"opendota-mcp-server: invalid settings\n{exc}")
    logging.basicConfig(
        stream=sys.stderr,
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if settings.mcp_transport == "http":
        # Serving HTTP before bearer auth exists would silently ignore MCP_AUTH_TOKEN.
        sys.exit("opendota-mcp-server: the HTTP transport is not available in this build yet")
    app = create_app(settings)
    logger.info("Starting opendota-mcp-server %s over stdio", __version__)
    app.run(transport="stdio", show_banner=False)
