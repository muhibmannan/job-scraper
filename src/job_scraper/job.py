from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    posted_date: str = ""
    source: str = "gradconnection"
    scraped_at: datetime = field(default_factory=datetime.now)