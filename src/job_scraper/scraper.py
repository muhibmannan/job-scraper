import re
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
import json

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

# Marker for the SPA's hydrated Redux state assignment in the page HTML.
_STATE_MARKER = "window.__initialState__"


def extract_precise_close_times(html: str) -> dict[str, datetime]:
    """Pull precise ISO 8601 closing timestamps from GradConnection's
    hydrated Redux state. Returns a dict keyed by campaign slug.

    Returns an empty dict if the state blob isn't present or can't be
    parsed (e.g., page format changes upstream) — callers should fall
    back to text parsing.
    """
    start = html.find(_STATE_MARKER)
    if start == -1:
        return {}

    brace_start = html.find("{", start)
    if brace_start == -1:
        return {}

    # The state blob is JS object-literal syntax, not strict JSON — it
    # uses JavaScript `undefined` for missing values, which json.loads
    # rejects. Convert to `null` before parsing.
    blob = re.sub(r"\bundefined\b", "null", html[brace_start:])

    try:
        state, _ = json.JSONDecoder().raw_decode(blob)
    except json.JSONDecodeError:
        return {}

    result: dict[str, datetime] = {}
    for group in state.get("campaigngroupstore", {}).get("campaignGroups", []):
        for c in group.get("campaigns", []):
            slug = c.get("slug")
            end_raw = (c.get("interval") or {}).get("end")
            if slug and end_raw:
                try:
                    result[slug] = datetime.fromisoformat(
                        end_raw.replace("Z", "+00:00")
                    )
                except ValueError:
                    continue
    return result


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
        precise_close_times = extract_precise_close_times(html)
        jobs = []

        for card in cards:
            job = self._parse_card(card, category, precise_close_times)
            if job is not None:
                jobs.append(job)

        return jobs

    def _parse_card(self, card, category: str, precise_close_times: dict[str, datetime]) -> Job | None:
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

        # Prefer the precise ISO 8601 timestamp from the SPA's hydrated state;
        # fall back to parsing the rounded "Closing in N <unit>" text.
        scraped_at = datetime.now(timezone.utc)
        slug = url.rstrip("/").rsplit("/", 1)[-1] if "/" in url else None
        if slug and slug in precise_close_times:
            closing_at = precise_close_times[slug]
        else:
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