"""
OpenDota MCP Server - Deployment Ready
Works with Claude Desktop (stdio) AND Cloud Run (HTTP)
"""
import logging
import os
import sys
from contextlib import asynccontextmanager
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
async def app_lifespan(server: FastMCP):
    """FastMCP lifespan management"""
    logger.info("Starting OpenDota MCP server...")
    
    # Startup
    await load_reference_data()
    register_all_tools(server)
    logger.info("SUCCESS: All tools registered")
    
    try:
        yield  # Server runs here
    finally:
        await cleanup_http_client()
        logger.info("Server shutdown complete")

# Create server with lifespan
mcp = FastMCP("OpenDota API Server", lifespan=app_lifespan)

@mcp.app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    return {"status": "healthy", "service": "opendota-mcp"}

# Debug endpoint - shows registered tools
@mcp.app.get("/debug/tools")
async def list_tools():
    """List all registered MCP tools"""
    try:
        # Get tools from the MCP server
        tools = []
        if hasattr(mcp, '_mcp_server') and hasattr(mcp._mcp_server, 'list_tools'):
            tool_list = await mcp._mcp_server.list_tools()
            tools = [{"name": t.name, "description": t.description[:100]} for t in tool_list.tools]
        
        return {
            "status": "ok",
            "tool_count": len(tools),
            "tools": tools
        }
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        return {"status": "error", "message": str(e)}

# Debug endpoint - echo request details
@mcp.app.post("/debug/echo")
async def echo_request(request: Request):
    """Echo back request details for debugging"""
    body = await request.body()
    return {
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers),
        "body_size": len(body),
        "body_preview": body.decode('utf-8', errors='ignore')[:500],
        "client": request.client.host if request.client else None
    }

# Request logging middleware
@mcp.app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests for debugging"""
    start_time = datetime.utcnow()
    
    # Log request
    logger.info(f"→ {request.method} {request.url.path}")
    
    # Only log body for non-health endpoints to reduce noise
    if request.url.path not in ["/health"]:
        body = await request.body()
        logger.debug(f"Request body size: {len(body)} bytes")
        if body:
            logger.debug(f"Body preview: {body.decode('utf-8', errors='ignore')[:200]}")
    
    try:
        response = await call_next(request)
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"← {request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)")
        return response
    except Exception as e:
        logger.error(f"Request failed: {str(e)}", exc_info=True)
        return Response(content=str(e), status_code=500)
        
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