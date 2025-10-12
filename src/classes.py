from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

@dataclass
class Player:
    account_id : int
    personaname: Optional[str] = None
    avatarfull: Optional[str] = None
    profileurl: Optional[str] = None
    win_count: Optional[int] = None
    lose_count: Optional[int] = None
    win_rate: Optional[float] = None
    fav_heroes: Optional[List[str]] = None
    
    def calculate_win_rate(self):
        """Calculate win rate from win and lose counts"""
        if self.win_count is not None and self.lose_count is not None:
            total = self.win_count + self.lose_count
            if total > 0:
                self.win_rate = round((self.win_count / total) * 100, 2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Player to dictionary, removing None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}

@dataclass
class Hero:
    id: int
    name: str
    localized_name: str
    primary_attr: str
    attack_type: str
    roles: List[str]