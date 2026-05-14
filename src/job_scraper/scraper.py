import re
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from .job import Job


# Regex captures the number and unit from "Closing in N <unit>".
# Handles "Closing in a day" / "Closing in an hour" by treating "a"/"an" as 1.
_CLOSING_RE = re.compile(
    r"closing in\s+(?P<num>\d+|a|an)\s+(?P<unit>hour|hours|day|days|week|weeks|month|months|year|years)",
    re.IGNORECASE,
)

# How many days each unit represents.
_UNIT_DAYS = {
    "hour": 1 / 24,
    "hours": 1 / 24,
    "day": 1,
    "days": 1,
    "week": 7,
    "weeks": 7,
    "month": 30,
    "months": 30,
    "year": 365,
    "years": 365,
}


def parse_closing_in(text: str, scraped_at: datetime) -> datetime | None:
    """Convert GradConnection's 'Closing in N <unit>' text into an absolute
    datetime relative to scrape time. Returns None if the text doesn't match
    (e.g., 'New!' or empty).
    """
    if not text:
        return None

    match = _CLOSING_RE.search(text)
    if not match:
        return None

    num_raw = match.group("num").lower()
    unit = match.group("unit").lower()

    if num_raw in ("a", "an"):
        num = 1
    else:
        num = int(num_raw)

    days = num * _UNIT_DAYS[unit]
    return scraped_at + timedelta(days=days)


class Scraper:
    """Scrapes graduate jobs and internships from GradConnection."""

    BASE_URLS = {
        "graduate": "https://au.gradconnection.com/graduate-jobs/computer-science/sydney/",
        "internship": "https://au.gradconnection.com/internships/computer-science/sydney/",
    }

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    BASE_DOMAIN = "https://au.gradconnection.com"

    def __init__(self, category: str = "both"):
        valid = {"graduate", "internship", "both"}
        if category not in valid:
            raise ValueError(f"category must be one of {valid}, got {category!r}")
        self.category = category

    def _categories_to_scrape(self) -> list[str]:
        if self.category == "both":
            return ["graduate", "internship"]
        return [self.category]

    def fetch(self, url: str) -> str:
        """Fetch raw HTML for a given URL. Raises on HTTP errors."""
        response = requests.get(url, headers=self.HEADERS, timeout=30)
        response.raise_for_status()
        return response.text

    def parse(self, html: str, category: str) -> list[Job]:
        """Parse HTML and return a list of Job objects."""
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("div.campaign-listing-box")
        jobs = []

        for card in cards:
            job = self._parse_card(card, category)
            if job is not None:
                jobs.append(job)

        return jobs

    def _parse_card(self, card, category: str) -> Job | None:
        """Extract a single Job from one card's BeautifulSoup element."""
        title_link = card.select_one("a.box-header-title")
        if title_link is None:
            return None

        title = title_link.get_text(strip=True)
        href = title_link.get("href", "")
        url = self.BASE_DOMAIN + href if href.startswith("/") else href

        company_el = card.select_one(".box-employer-name a p")
        company = company_el.get_text(strip=True) if company_el else "Unknown"

        location_el = card.select_one(".location-name")
        if location_el is not None:
            # Grab only the direct text node, skipping nested tooltip content
            direct_text = location_el.find(string=True, recursive=False)
            location = direct_text.strip() if direct_text else ""
        else:
            location = ""

        closing_el = card.select_one(".closing-in")
        posted_date = closing_el.get_text(strip=True) if closing_el else ""

        desc_el = card.select_one(".box-description-para")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # Compute absolute closing timestamp from the relative text.
        scraped_at = datetime.now(timezone.utc)
        closing_at = parse_closing_in(posted_date, scraped_at)

        return Job(
            title=title,
            company=company,
            location=location,
            url=url,
            description=description,
            posted_date=posted_date,
            closing_at=closing_at,
            source=f"gradconnection-{category}",
            scraped_at=scraped_at,
        )

    def scrape(self) -> list[Job]:
        """Run the full scrape: fetch + parse for each requested category."""
        all_jobs: list[Job] = []
        for category in self._categories_to_scrape():
            url = self.BASE_URLS[category]
            print(f"Fetching {category} jobs...")
            html = self.fetch(url)
            jobs = self.parse(html, category)
            print(f"  Parsed {len(jobs)} {category} jobs")
            all_jobs.extend(jobs)
            time.sleep(1)  # be polite, don't hammer the server
        return all_jobs