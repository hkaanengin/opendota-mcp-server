"""
OpenDota MCP Server - Main Entry Point
Supports stdio (local), SSE, and HTTP transports
"""
import logging
import os
import asyncio
import sys
from fastmcp import FastMCP
import uvicorn

# Setup logging - DON'T log to stdout (MCP uses it for JSON)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()

# Log to stderr instead of stdout for MCP compatibility
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger("opendota-server")

# Initialize MCP server
mcp = FastMCP("OpenDota API Server")

# Import and register all tools
from .tools import register_all_tools
from .client import cleanup_http_client
from .utils import load_reference_data


async def lifespan_startup():
    """Initialize on startup"""
    logger.info("=" * 60)
    logger.info("Starting OpenDota MCP server...")
    logger.info("=" * 60)
    
    # Load reference data on startup
    logger.info("Initializing reference data...")
    await load_reference_data()
    
    # Register all tools
    logger.info("Registering MCP tools...")
    register_all_tools(mcp)
    logger.info("SUCCESS: All tools registered successfully")
    
    logger.info("=" * 60)
    logger.info("READY: Server is ready to accept requests!")
    logger.info("=" * 60)


async def lifespan_shutdown():
    """Cleanup on shutdown"""
    logger.info("Cleaning up resources...")
    await cleanup_http_client()
    logger.info("SUCCESS: Server shutdown complete")


def main():
    """Main entry point for the MCP server"""
    
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    port = int(os.getenv("PORT", "8080"))
    
    if transport in ["sse", "http"]:
        logger.info(f"Starting in {transport.upper()} mode on 0.0.0.0:{port}")
        
        # Run startup tasks
        asyncio.run(lifespan_startup())
        
        try:
            # Choose the appropriate app based on transport
            if transport == "sse":
                app = mcp.sse_app()
                logger.info("Using SSE transport")
            else:  # http
                app = mcp.create_app()
                logger.info("Using HTTP transport")
            
            # Start HTTP server
            uvicorn.run(
                app,
                host="0.0.0.0",
                port=port,
                log_level="info"
            )
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"ERROR: Server error: {e}", exc_info=True)
        finally:
            asyncio.run(lifespan_shutdown())
    else:
        logger.info("Starting in stdio mode for local development")
        
        asyncio.run(lifespan_startup())
        
        try:
            mcp.run()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"ERROR: Server error: {e}", exc_info=True)
        finally:
            asyncio.run(lifespan_shutdown())

if __name__ == '__main__':
    main()