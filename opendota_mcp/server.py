"""
OpenDota MCP Server - Working Version with Deep Hook
"""
import logging
import os
import sys
from contextlib import asynccontextmanager
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

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

class InjectAcceptHeaderASGIMiddleware:
    """
    ASGI middleware that injects Accept header at the lowest level.
    This ensures it works regardless of how FastMCP sets up its apps.
    """
    def __init__(self, app: ASGIApp):
        self.app = app
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and scope["path"] == "/mcp":
            logger.info(f"🔍 ASGI: Intercepting /mcp request")
            
            headers = dict(scope.get("headers", []))
            
            accept_modified = False
            new_headers = []
            
            for name, value in headers.items():
                if name == b"accept":
                    accept_value = value.decode()
                    if "text/event-stream" not in accept_value:
                        accept_value = f"{accept_value}, text/event-stream"
                        logger.info(f"🔧 ASGI: Modified Accept header")
                    new_headers.append((name, accept_value.encode()))
                    accept_modified = True
                else:
                    new_headers.append((name, value))
            
            if not accept_modified:
                new_headers.append((b"accept", b"application/json, text/event-stream"))
                logger.info(f"🔧 ASGI: Added Accept header")
            
            scope["headers"] = new_headers
        
        await self.app(scope, receive, send)

logger.info("Setting up Claude.ai compatibility at ASGI level...")

_original_fastapi_init = FastAPI.__init__

def _patched_fastapi_init(self, *args, **kwargs):
    """Patched FastAPI.__init__ that wraps the ASGI app"""
    _original_fastapi_init(self, *args, **kwargs)
    
    original_app = self.app
    self.app = InjectAcceptHeaderASGIMiddleware(original_app)
    logger.info(f"✅ ASGI middleware injected into FastAPI instance")

FastAPI.__init__ = _patched_fastapi_init
logger.info("✅ Monkey-patched FastAPI with ASGI middleware")

@asynccontextmanager
async def app_lifespan(server):
    """FastMCP lifespan management"""
    logger.info("Starting OpenDota MCP server...")
    
    await load_reference_data()
    register_all_tools(server)
    logger.info("SUCCESS: All tools registered")
    
    try:
        yield  # Server runs here
    finally:
        await cleanup_http_client()
        logger.info("Server shutdown complete")

mcp = FastMCP("OpenDota API Server", lifespan=app_lifespan)

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    """Health check endpoint for Cloud Run"""
    return JSONResponse({"status": "healthy", "service": "opendota-mcp"})

@mcp.custom_route("/debug/tools", methods=["GET"])
async def list_tools(request: Request):
    """List all registered MCP tools"""
    try:
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
        logger.info(f"Starting HTTP server on 0.0.0.0:{port}")
        mcp.run(transport="http", host="0.0.0.0", port=port)
    else:
        logger.info("Starting in stdio mode for Claude Desktop")
        mcp.run()

if __name__ == '__main__':
    main()