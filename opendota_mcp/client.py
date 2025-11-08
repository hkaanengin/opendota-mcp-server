"""
HTTP client and rate limiter management
"""
import httpx
import logging
from typing import Optional, Dict, Any
from .classes import RateLimiter
from .config import OPENDOTA_BASE_URL, RATE_LIMIT_RPM, OPENDOTA_API_KEY

logger = logging.getLogger("opendota-server")

# Global instances
rate_limiter = RateLimiter(requests_per_minute=RATE_LIMIT_RPM)
http_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    """Get or create the async HTTP client."""
    global http_client
    if http_client is None:
        headers = {}

        # Add API key to Authorization header if available
        if OPENDOTA_API_KEY:
            headers["Authorization"] = f"Bearer {OPENDOTA_API_KEY}"
            logger.info("HTTP client initialized with API key authentication")
        else:
            logger.info("HTTP client initialized (anonymous access)")

        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=120.0,
                write=10.0,
                pool=10.0
            ),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            headers=headers
        )
    return http_client


async def cleanup_http_client():
    """Close the HTTP client on shutdown."""
    global http_client
    if http_client is not None:
        await http_client.aclose()
        http_client = None
        logger.info("HTTP client closed")


async def fetch_api(endpoint: str, params: Dict[str, Any] = None) -> dict:
    """
    Fetch data from OpenDota API with rate limiting.

    API key is automatically included via Authorization header if configured.

    Args:
        endpoint: API endpoint path
        params: Query parameters

    Returns:
        JSON response from API
    """
    client = await get_http_client()
    await rate_limiter.acquire()

    if params is None:
        params = {}

    url = f"{OPENDOTA_BASE_URL}{endpoint}"
    logger.info(f"Fetching data from {url}, with params: {params}")

    response = await client.get(url, params=params)
    response.raise_for_status()

    logger.info(f"Received response status: {response.status_code}")
    return response.json()