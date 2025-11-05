from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
import asyncio
from datetime import datetime, timedelta
import logging
import time
from collections import defaultdict

logger = logging.getLogger("opendota-server")

@dataclass
class Player:
    account_id : int
    personaname: Optional[str] = None
    avatarfull: Optional[str] = None
    profileurl: Optional[str] = None
    win_count: Optional[int] = None
    lose_count: Optional[int] = None
    win_rate: Optional[float] = None
    fav_heroes: Optional[List[Dict[str, Any]]] = None
    
    def calculate_win_rate(self):
        """Calculate win rate from win and lose counts"""
        if self.win_count is not None and self.lose_count is not None:
            total = self.win_count + self.lose_count
            if total > 0:
                self.win_rate = round((self.win_count / total) * 100, 2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Player to dictionary, removing None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}

# Rate limiter configuration
class RateLimiter:
    """
    Simple rate limiter for OpenDota API.
    OpenDota has rate limits: 60 requests per minute for anonymous users.
    """
    def __init__(self, requests_per_minute: int = 50):
        """
        Args:
            requests_per_minute: Maximum requests allowed per minute (default 50 to be safe)
        """
        self.requests_per_minute = requests_per_minute
        self.requests = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait if necessary to respect rate limits."""
        async with self.lock:
            now = datetime.now()
            # Remove requests older than 1 minute
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < timedelta(minutes=1)]
            
            if len(self.requests) >= self.requests_per_minute:
                # Calculate wait time
                oldest_request = self.requests[0]
                wait_time = 60 - (now - oldest_request).total_seconds()
                if wait_time > 0:
                    logger.warning(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
                    await asyncio.sleep(wait_time)
                    # Clean up again after waiting
                    now = datetime.now()
                    self.requests = [req_time for req_time in self.requests 
                                   if now - req_time < timedelta(minutes=1)]
            
            # Add current request
            self.requests.append(now)

#Server Metrics for server.py
class ServerMetrics:
    """Simple in-memory metrics for debugging"""
    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.tool_calls = defaultdict(int)
        self.errors = []
        self.last_requests = []
        self.active_connections = 0
        
    def record_request(self, method: str, path: str):
        self.request_count += 1
        self.last_requests.append({
            "timestamp": datetime.utcnow().isoformat(),
            "method": method,
            "path": path
        })
        # Keep only last 50 requests
        if len(self.last_requests) > 50:
            self.last_requests.pop(0)
    
    def record_tool_call(self, tool_name: str):
        self.tool_calls[tool_name] += 1
    
    def record_error(self, error: str, context: str = None):
        self.errors.append({
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(error),
            "context": context
        })
        # Keep only last 100 errors
        if len(self.errors) > 100:
            self.errors.pop(0)
    
    def get_uptime(self):
        return time.time() - self.start_time
    
    def to_dict(self):
        return {
            "uptime_seconds": round(self.get_uptime(), 2),
            "total_requests": self.request_count,
            "tool_calls": dict(self.tool_calls),
            "recent_errors": self.errors[-10:],  # Last 10 errors
            "last_requests": self.last_requests[-10:],  # Last 10 requests
            "active_connections": self.active_connections
        }