"""MCP tools, one module per area. Each tool is thin: resolve → fetch → shape."""

from fastmcp import FastMCP

from opendota_mcp.api import OpenDotaClient
from opendota_mcp.reference import Reference
from opendota_mcp.tools.records import register_records_tools


def register_all_tools(mcp: FastMCP, api: OpenDotaClient, reference: Reference) -> None:
    register_records_tools(mcp, api, reference)
