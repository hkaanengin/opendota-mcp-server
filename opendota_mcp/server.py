"""
OpenDota MCP Server - Multi-Transport Support with Enhanced Debugging
"""
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from collections import defaultdict
from datetime import datetime
from fastapi import Request
from fastapi.responses import JSONResponse
from fastmcp import FastMCP

# Logging setup with more detail
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stderr)]
)

logger = logging.getLogger("opendota-server")

from .tools import register_all_tools
from .client import cleanup_http_client
from .utils import load_reference_data
from .classes import ServerMetrics

metrics = ServerMetrics()

# ============================================================================
# Lifespan and Setup
# ============================================================================

@asynccontextmanager
async def app_lifespan(server):
    """FastMCP lifespan management"""
    logger.info("=" * 60)
    logger.info("Starting OpenDota MCP server...")
    logger.info(f"Transport: {os.getenv('MCP_TRANSPORT', 'auto')}")
    logger.info(f"Log Level: {log_level}")
    logger.info("=" * 60)
    
    try:
        await load_reference_data()
        logger.info("✅ Reference data loaded")
        
        register_all_tools(server)
        logger.info("✅ All tools registered")
        
        logger.info("=" * 60)
        logger.info("🚀 Server ready to accept connections")
        logger.info("=" * 60)
        
        yield  # Server runs here
        
    except Exception as e:
        logger.error(f"❌ Fatal error during startup: {e}", exc_info=True)
        metrics.record_error(e, "startup")
        raise
    finally:
        logger.info("Shutting down server...")
        await cleanup_http_client()
        logger.info("✅ Server shutdown complete")

mcp = FastMCP("OpenDota API Server", lifespan=app_lifespan)

# ============================================================================
# Request Logging Middleware
# ============================================================================

@mcp.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    start_time = time.time()
    
    # Log request
    logger.info(f"→ {request.method} {request.url.path}")
    logger.debug(f"  Headers: {dict(request.headers)}")
    metrics.record_request(request.method, request.url.path)
    
    # Process request
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(f"← {request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)")
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"← {request.method} {request.url.path} - ERROR ({duration:.3f}s): {e}", exc_info=True)
        metrics.record_error(e, f"{request.method} {request.url.path}")
        raise

# ============================================================================
# Debug Endpoints
# ============================================================================

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    """Health check endpoint for Cloud Run and monitoring"""
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    uptime = metrics.get_uptime()
    
    return JSONResponse({
        "status": "healthy",
        "service": "opendota-mcp",
        "transport": transport,
        "uptime_seconds": round(uptime, 2),
        "uptime_human": f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m",
        "total_requests": metrics.request_count,
        "timestamp": datetime.utcnow().isoformat()
    })

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
                tools = [
                    {
                        "name": t.name,
                        "description": t.description[:100] if t.description else "",
                        "call_count": metrics.tool_calls.get(t.name, 0)
                    } 
                    for t in tool_list.tools
                ]
        
        return JSONResponse({
            "status": "ok",
            "tool_count": len(tools),
            "tools": tools,
            "total_tool_calls": sum(metrics.tool_calls.values())
        })
    except Exception as e:
        logger.error(f"Error listing tools: {e}", exc_info=True)
        metrics.record_error(e, "list_tools")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@mcp.custom_route("/debug/metrics", methods=["GET"])
async def get_metrics(request: Request):
    """Get server metrics and statistics"""
    return JSONResponse(metrics.to_dict())

@mcp.custom_route("/debug/logs", methods=["GET"])
async def get_recent_logs(request: Request):
    """Get recent errors and requests"""
    return JSONResponse({
        "recent_requests": metrics.last_requests[-20:],
        "recent_errors": metrics.errors[-20:],
        "error_count": len(metrics.errors)
    })

@mcp.custom_route("/", methods=["GET"])
async def root(request: Request):
    """Root endpoint with usage instructions"""
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    
    return JSONResponse({
        "service": "OpenDota MCP Server",
        "version": "1.0.0",
        "transport": transport,
        "status": "running",
        "uptime_seconds": round(metrics.get_uptime(), 2),
        "endpoints": {
            "health": "/health",
            "tools": "/debug/tools",
            "metrics": "/debug/metrics",
            "logs": "/debug/logs",
            "mcp_sse": "/sse" if transport == "sse" else None,
        },
        "documentation": {
            "stdio": "For local use with Claude Desktop - configure in claude_desktop_config.json",
            "sse": "For web use with Claude.ai - add as MCP server with this URL",
            "setup": "See README.md for configuration instructions"
        }
    })

# ============================================================================
# Tool Call Monitoring (Hook into FastMCP)
# ============================================================================

# Wrap tool registration to add monitoring
_original_register = register_all_tools

def register_all_tools_with_monitoring(server):
    """Wrap tool registration to add call monitoring"""
    _original_register(server)
    
    # Log registered tools
    if hasattr(server, '_mcp_server') and hasattr(server._mcp_server, 'list_tools'):
        import inspect
        list_tools_func = server._mcp_server.list_tools
        
        if inspect.iscoroutinefunction(list_tools_func):
            import asyncio
            tool_list = asyncio.run(list_tools_func())
        else:
            tool_list = list_tools_func()
        
        if hasattr(tool_list, 'tools'):
            logger.info(f"📦 Registered {len(tool_list.tools)} tools:")
            for tool in tool_list.tools:
                logger.info(f"   - {tool.name}")

# Replace with monitoring version
register_all_tools = register_all_tools_with_monitoring

# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """
    Main entry point with intelligent transport selection
    
    Environment Variables:
        MCP_TRANSPORT: "stdio" (default), "sse", or "auto"
        PORT: Port for SSE server (default: 8080)
        HOST: Host for SSE server (default: 0.0.0.0)
        LOG_LEVEL: Logging level (default: INFO)
    """
    transport = os.getenv("MCP_TRANSPORT", "auto").lower()
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    
    if transport == "auto":
        if "PORT" in os.environ or "K_SERVICE" in os.environ or "CLOUD_RUN" in os.environ:
            transport = "sse"
            logger.info("🔍 Auto-detected cloud environment, using SSE transport")
        else:
            transport = "stdio"
            logger.info("🔍 Auto-detected local environment, using stdio transport")
    
    if transport == "sse":
        logger.info("=" * 60)
        logger.info("🌐 Starting SSE server")
        logger.info(f"   Host: {host}")
        logger.info(f"   Port: {port}")
        logger.info(f"   MCP endpoint: http://{host}:{port}/sse")
        logger.info(f"   Health check: http://{host}:{port}/health")
        logger.info(f"   Metrics: http://{host}:{port}/debug/metrics")
        logger.info(f"   Logs: http://{host}:{port}/debug/logs")
        logger.info("=" * 60)
        mcp.run(transport="sse", host=host, port=port)
    
    elif transport == "stdio":
        logger.info("=" * 60)
        logger.info("🖥️  Starting in stdio mode for Claude Desktop")
        logger.info("   Configure this in your claude_desktop_config.json")
        logger.info("=" * 60)
        mcp.run(transport="stdio")
    
    else:
        logger.error(f"❌ Unknown transport: {transport}")
        logger.error("   Valid options: 'stdio', 'sse', or 'auto'")
        sys.exit(1)

if __name__ == '__main__':
    main()