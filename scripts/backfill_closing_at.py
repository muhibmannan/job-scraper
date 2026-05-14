"""One-off backfill: populate closing_at for rows that pre-date migration 002.

Reads each row where closing_at IS NULL, parses its original posted_date
string against the row's own scraped_at, and writes the computed timestamp
back to the row. Rows with unparseable posted_date text (e.g., "New!" or
empty) stay NULL.

Run once after applying migration 002:
    PYTHONPATH=src .venv/bin/python scripts/backfill_closing_at.py
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from job_scraper.database import Database
from job_scraper.scraper import parse_closing_in


def main() -> int:
    db = Database()

    with db._cursor() as cur:
        cur.execute(
            """
            SELECT id, posted_date, scraped_at
            FROM scraped_jobs
            WHERE closing_at IS NULL
            ORDER BY scraped_at DESC
            """
        )
        rows = cur.fetchall()

    if not rows:
        print("No rows to backfill — all closing_at values populated.")
        db.close()
        return 0

    print(f"Found {len(rows)} rows with NULL closing_at\n")

    updated = 0
    unparseable = 0

    for row in rows:
        text = row["posted_date"] or ""
        scraped_at = row["scraped_at"]
        closing_at = parse_closing_in(text, scraped_at)

        if closing_at is None:
            unparseable += 1
            print(f"  [skip] id={row['id']} posted_date={text!r} (unparseable)")
            continue

        with db._cursor() as cur:
            cur.execute(
                "UPDATE scraped_jobs SET closing_at = %s WHERE id = %s",
                (closing_at, row["id"]),
            )
        updated += 1

    print(f"\nBackfilled {updated} rows. {unparseable} left NULL (unparseable).")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())