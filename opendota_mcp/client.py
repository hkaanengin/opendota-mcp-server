"""
HTTP client and rate limiter management
"""
import httpx # type: ignore
import logging
from typing import Optional
from .classes import RateLimiter
from .config import OPENDOTA_BASE_URL, RATE_LIMIT_RPM

logger = logging.getLogger("opendota-server")

# Global instances
rate_limiter = RateLimiter(requests_per_minute=RATE_LIMIT_RPM)
http_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    """Get or create the async HTTP client."""
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        logger.info("HTTP client initialized")
    return http_client


async def cleanup_http_client():
    """Close the HTTP client on shutdown."""
    global http_client
    if http_client is not None:
        await http_client.aclose()
        http_client = None
        logger.info("HTTP client closed")


async def fetch_api(endpoint: str, params: dict = None) -> dict:
    """
    Fetch data from OpenDota API with rate limiting.
    
    Args:
        endpoint: API endpoint path
        params: Query parameters
    
    Returns:
        JSON response from API
    """
    client = await get_http_client()
    await rate_limiter.acquire()
    
    url = f"{OPENDOTA_BASE_URL}{endpoint}"
    logger.info(f"Fetching data from {url}, with params: {params}")
    
    response = await client.get(url, params=params)
    response.raise_for_status()
    
    logger.info(f"Received response status: {response.status_code}")
    return response.json()