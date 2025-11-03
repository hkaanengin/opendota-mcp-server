"""
OpenDota MCP Server Package
"""
__version__ = "1.0.0"

try:
    from .server import main, mcp
    __all__ = ["main", "mcp"]
except ImportError as e:
    print(f"Warning: Could not import server components: {e}")
    __all__ = []