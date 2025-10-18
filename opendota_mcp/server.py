"""
OpenDota MCP Server - Main Entry Point
"""
import logging
import os
import asyncio
from fastmcp import FastMCP #type: ignore

# Setup logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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
    logger.info("Starting OpenDota MCP server...")
    
    # Load reference data on startup
    asyncio.run(load_reference_data())
    
    # Register all tools
    register_all_tools(mcp)
    
    try:
        # Start the MCP server
        mcp.run()
    finally:
        # Cleanup on shutdown
        asyncio.run(cleanup_http_client())
        logger.info("Server shutdown complete")


if __name__ == '__main__':
    main()