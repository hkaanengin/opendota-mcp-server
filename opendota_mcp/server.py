"""
OpenDota MCP Server - Deployment Ready
Works with Claude Desktop (stdio) AND Cloud Run (HTTP)
"""
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from fastmcp import FastMCP

# Setup logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stderr)]
)

logger = logging.getLogger("opendota-server")

from .tools import register_all_tools
from .client import cleanup_http_client
from .utils import load_reference_data

@asynccontextmanager
async def app_lifespan(server):
    """FastMCP lifespan management"""
    from .config import OPENDOTA_API_KEY

    logger.info("Starting OpenDota MCP server...")

    # Check API key status
    if OPENDOTA_API_KEY:
        logger.info("✅ OpenDota API key configured (higher rate limits enabled)")
    else:
        logger.info("ℹ️  No API key - using anonymous access (50 req/min)")

    # Startup
    load_reference_data()
    logger.info("✅ Reference data loaded")

    try:
        yield
    finally:
        await cleanup_http_client()
        logger.info("Server shutdown complete")

# Create server with lifespan
mcp = FastMCP("OpenDota API Server", lifespan=app_lifespan)

logger.info("Registering tools...")
register_all_tools(mcp)
logger.info("✅ Tools registered")

# Add custom routes using the @custom_route decorator
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    """Health check endpoint for Cloud Run"""
    return JSONResponse({"status": "healthy", "service": "opendota-mcp"})

@mcp.custom_route("/debug/tools", methods=["GET"])
async def list_tools(request: Request):
    """List all registered MCP tools with full descriptions and parameter schemas"""
    try:
        # Use the public get_tools() API (async)
        tools_dict = await mcp.get_tools()

        tools = []
        for name, tool in tools_dict.items():
            tool_info = {
                "name": tool.name,
                "description": tool.description or "No description"
            }

            # Include parameter schema for structured function calling
            if hasattr(tool, 'parameters') and tool.parameters:
                tool_info["parameters"] = tool.parameters
            elif hasattr(tool, 'inputSchema') and tool.inputSchema:
                tool_info["parameters"] = tool.inputSchema

            # No truncation - LLM benefits from full descriptions

            tools.append(tool_info)

        tool_count = len(tools)
        logger.info(f"Successfully listed {tool_count} registered tools")

        return JSONResponse({
            "status": "ok",
            "tool_count": tool_count,
            "tools": tools,
            "message": f"Found {tool_count} registered tools"
        })

    except Exception as e:
        logger.error(f"Error listing tools: {e}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e),
            "tool_count": 0,
            "tools": []
        }, status_code=500)

@mcp.custom_route("/debug/echo", methods=["POST"])
async def echo_request(request: Request):
    """Echo back request details for debugging"""
    body = await request.body()
    return JSONResponse({
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers),
        "body_size": len(body),
        "body_preview": body.decode('utf-8', errors='ignore')[:500],
        "client": request.client.host if request.client else None
    })

@mcp.custom_route("/call_tool", methods=["POST"])
async def call_tool_http(request: Request):
    try:
        body = await request.json()

        tool_name = body.get("tool_name")
        arguments = body.get("arguments", {})

        if not tool_name:
            return JSONResponse(
                {"status": "error", "message": "Missing tool_name"},
                status_code=400,
            )

        if not isinstance(arguments, dict):
            return JSONResponse(
                {"status": "error", "message": "arguments must be a dict"},
                status_code=400,
            )

        logger.info(f"HTTP tool call: {tool_name} with args: {arguments}")

        # 🔑 Get registered tools
        tools = await mcp.get_tools()

        if tool_name not in tools:
            return JSONResponse(
                {
                    "status": "error",
                    "message": f"Tool '{tool_name}' not found",
                },
                status_code=404,
            )

        tool = tools[tool_name]

        # 🔑 Call the tool function directly
        result = await tool.fn(**arguments)

        logger.info(f"Tool {tool_name} completed successfully")

        return JSONResponse(
            {
                "status": "success",
                "tool_name": tool_name,
                "result": result,
            }
        )

    except Exception as e:
        logger.error("Error calling tool via HTTP", exc_info=True)
        return JSONResponse(
            {
                "status": "error",
                "message": str(e),
                "tool_name": tool_name if "tool_name" in locals() else None,
            },
            status_code=500,
        )

def main():
    """Main entry point"""
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    port = int(os.getenv("PORT", "8080"))
    
    if transport == "http":
        # Cloud Run deployment - use HTTP
        logger.info(f"Starting HTTP server on 0.0.0.0:{port}")
        mcp.run(transport="http", host="0.0.0.0", port=port)
    else:
        # Local Claude Desktop - use stdio (default)
        logger.info("Starting in stdio mode for Claude Desktop")
        mcp.run()  # This uses stdio by default

if __name__ == '__main__':
    main()