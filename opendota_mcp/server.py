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
from starlette.middleware.base import BaseHTTPMiddleware

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

class InjectAcceptHeaderMiddleware(BaseHTTPMiddleware):
    """
    FastMCP requires 'text/event-stream' in Accept header, but Claude.ai doesn't send it.
    This middleware automatically adds it to fix compatibility.
    """
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/mcp":
            logger.info(f"🔍 Intercepting /mcp request")
            headers = dict(request.scope["headers"])
            
            accept_modified = False
            new_headers = []
            
            for name, value in headers.items():
                if name == b"accept":
                    accept_value = value.decode()
                    if "text/event-stream" not in accept_value:
                        accept_value = f"{accept_value}, text/event-stream"
                        logger.info(f"🔧 Modified Accept header")
                    new_headers.append((name, accept_value.encode()))
                    accept_modified = True
                else:
                    new_headers.append((name, value))
            
            if not accept_modified:
                new_headers.append((b"accept", b"application/json, text/event-stream"))
                logger.info(f"🔧 Added missing Accept header")
            
            request.scope["headers"] = new_headers
        
        response = await call_next(request)
        return response

@asynccontextmanager
async def app_lifespan(server):
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

# Add custom routes using the @custom_route decorator
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    """Health check endpoint for Cloud Run"""
    return JSONResponse({"status": "healthy", "service": "opendota-mcp"})

@mcp.custom_route("/debug/tools", methods=["GET"])
async def list_tools(request: Request):
    """List all registered MCP tools"""
    try:
        # Get tools from the MCP server
        tools = []
        if hasattr(mcp, '_mcp_server') and hasattr(mcp._mcp_server, 'list_tools'):
            import inspect
            list_tools_func = mcp._mcp_server.list_tools
            
            if inspect.iscoroutinefunction(list_tools_func):
                tool_list = await list_tools_func()
            else:
                tool_list = list_tools_func()
            
            if hasattr(tool_list, 'tools'):
                tools = [{"name": t.name, "description": t.description[:100] if t.description else ""} 
                        for t in tool_list.tools]
        
        return JSONResponse({
            "status": "ok",
            "tool_count": len(tools),
            "tools": tools
        })
    except Exception as e:
        logger.error(f"Error listing tools: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

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
        logger.info("Setting up Claude.ai compatibility...")
        
        middleware_status = {
            'http_app': False,
            'sse_app': False, 
            'streamable_http_app': False
        }
        
        if hasattr(mcp, 'http_app') and mcp.http_app is not None:
            mcp.http_app.add_middleware(InjectAcceptHeaderMiddleware)
            middleware_status['http_app'] = True
            logger.info("✅ Middleware added to http_app")
        
        if hasattr(mcp, 'sse_app') and mcp.sse_app is not None:
            mcp.sse_app.add_middleware(InjectAcceptHeaderMiddleware)
            middleware_status['sse_app'] = True
            logger.info("✅ Middleware added to sse_app")
        
        if hasattr(mcp, 'streamable_http_app') and mcp.streamable_http_app is not None:
            mcp.streamable_http_app.add_middleware(InjectAcceptHeaderMiddleware)
            middleware_status['streamable_http_app'] = True
            logger.info("✅ Middleware added to streamable_http_app (MCP handler)")
        
        active_apps = [name for name, status in middleware_status.items() if status]
        if active_apps:
            logger.info(f"✅ Middleware configured on: {', '.join(active_apps)}")
        else:
            logger.error("❌ WARNING: No middleware added - server may not work!")
        
        if not middleware_status['streamable_http_app']:
            logger.error("❌ CRITICAL: streamable_http_app missing - Claude.ai won't connect!")
        
        logger.info(f"Starting HTTP server on 0.0.0.0:{port}")
        mcp.run(transport="http", host="0.0.0.0", port=port)
    else:
        logger.info("Starting in stdio mode for Claude Desktop")
        mcp.run()

if __name__ == '__main__':
    main()