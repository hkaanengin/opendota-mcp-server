"""
OpenDota MCP Server - Main Entry Point
"""
import logging
import os
import asyncio
import sys
from fastmcp import FastMCP

# Setup logging - DON'T log to stdout (MCP uses it for JSON)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()

# Log to stderr instead of stdout for MCP compatibility
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stderr)  # Use stderr, not stdout!
    ]
)

logger = logging.getLogger("opendota-server")

# Initialize MCP server
mcp = FastMCP("OpenDota API Server")

# Import and register all tools
from .tools import register_all_tools
from .client import cleanup_http_client
from .utils import load_reference_data


def main():
    """Main entry point for the MCP server"""
    logger.info("=" * 60)
    logger.info("Starting OpenDota MCP server...")
    logger.info("=" * 60)
    
    # Load reference data on startup
    logger.info("Initializing reference data...")
    asyncio.run(load_reference_data())
    
    # Register all tools
    logger.info("Registering MCP tools...")
    register_all_tools(mcp)
    logger.info("SUCCESS: All tools registered successfully")
    
    logger.info("=" * 60)
    logger.info("READY: Server is ready to accept requests!")
    logger.info("=" * 60)
    
    try:
        # Start the MCP server
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"ERROR: Server error: {e}", exc_info=True)
    finally:
        # Cleanup on shutdown
        logger.info("Cleaning up resources...")
        asyncio.run(cleanup_http_client())
        logger.info("SUCCESS: Server shutdown complete")


if __name__ == '__main__':
    main()