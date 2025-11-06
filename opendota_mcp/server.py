"""
OpenDota MCP Server - Deployment Ready
Works with Claude Desktop (stdio) AND Cloud Run (HTTP)
"""
import logging
import os
from re import L
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
    logger.info("Starting OpenDota MCP server...")
    
    # Startup
    await load_reference_data()
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
    """List all registered MCP tools"""
    try:
        tools = []
        tool_count = 0
        
        if hasattr(mcp, '_mcp_server'):
            mcp_server = mcp._mcp_server
            logger.info(f"Found _mcp_server: {type(mcp_server)}")
            
            if hasattr(mcp_server, 'list_tools'):
                try:
                    # Call the function (it might be async)
                    tool_list_result = mcp_server.list_tools()
                    logger.info(f"list_tools() returned: {type(tool_list_result)}")
                    
                    # Check if it's a coroutine (async function)
                    if hasattr(tool_list_result, '__await__'):
                        tool_list_result = await tool_list_result
                        logger.info(f"After await: {type(tool_list_result)}")
                    
                    # Now check if result has 'tools' attribute
                    if hasattr(tool_list_result, 'tools'):
                        for t in tool_list_result.tools:
                            tool_info = {
                                "name": getattr(t, 'name', 'unknown'),
                                "description": "No description"
                            }
                            
                            if hasattr(t, 'description') and t.description:
                                desc = str(t.description)
                                tool_info["description"] = desc[:100] + ("..." if len(desc) > 100 else "")
                            
                            tools.append(tool_info)
                        tool_count = len(tools)
                        logger.info(f"Successfully extracted {tool_count} tools")
                    else:
                        logger.warning(f"tool_list_result has no 'tools' attribute. Attributes: {dir(tool_list_result)}")
                        
                except Exception as e:
                    logger.error(f"Error calling list_tools(): {e}", exc_info=True)
            else:
                logger.warning("_mcp_server has no 'list_tools' method")
        else:
            logger.warning("mcp has no '_mcp_server' attribute")

        return JSONResponse({
            "status": "ok" if tool_count > 0 else "warning",
            "tool_count": tool_count,
            "tools": tools,
            "message": f"Found {tool_count} registered tools" if tool_count > 0 else "No tools found"
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in list_tools endpoint: {e}", exc_info=True)
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