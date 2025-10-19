from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
import asyncio
from datetime import datetime, timedelta

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
                    print(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
                    await asyncio.sleep(wait_time)
                    # Clean up again after waiting
                    now = datetime.now()
                    self.requests = [req_time for req_time in self.requests 
                                   if now - req_time < timedelta(minutes=1)]
            
            # Add current request
            self.requests.append(now)