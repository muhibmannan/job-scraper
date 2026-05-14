from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    posted_date: str = ""
    closing_at: datetime | None = None
    source: str = "gradconnection"
    scraped_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )