from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class Event:
    """Shared event model used by all scrapers."""
    title: str
    description: str
    url: str
    source: str

    location: str = ""
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    price_text: str = ""
    is_free: bool = False
    categories: List[str] = field(default_factory=list)
    image_url: Optional[str] = None

    # Populated after AI filtering
    ai_category: str = ""
    ai_priority: int = 2        # 1 = high, 2 = medium, 3 = low
    ai_location_region: str = ""
