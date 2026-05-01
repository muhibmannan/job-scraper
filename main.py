import argparse
import sys

from src.job_scraper.database import Database
from src.job_scraper.scraper import Scraper


def cmd_scrape(args: argparse.Namespace) -> int:
    """Scrape jobs and save to the database."""
    scraper = Scraper(category=args.category)
    db = Database(args.db)

    try:
        jobs = scraper.scrape()
    except Exception as e:
        print(f"Scrape failed: {e}", file=sys.stderr)
        return 1

    inserted = 0
    duplicates = 0
    for job in jobs:
        if db.save_job(job):
            inserted += 1
        else:
            duplicates += 1

    print(f"\nDone: {inserted} new, {duplicates} duplicates, {db.count()} total in DB")
    db.close()
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List all jobs in the database."""
    db = Database(args.db)
    jobs = db.get_all_jobs()

    if not jobs:
        print("No jobs in database. Run `scrape` first.")
        db.close()
        return 0

    print(f"{len(jobs)} jobs in database:\n")
    for job in jobs[:args.limit]:
        print(f"- {job['title']}")
        print(f"  {job['company']} | {job['location']} | {job['source']}")
        print(f"  {job['url']}")
        print()

    if len(jobs) > args.limit:
        print(f"... and {len(jobs) - args.limit} more (use --limit to see more)")

    db.close()
    return 0


def cmd_count(args: argparse.Namespace) -> int:
    """Print the number of jobs in the database."""
    db = Database(args.db)
    print(db.count())
    db.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="job-scraper",
        description="Scrape Australian graduate SWE jobs into a local SQLite DB.",
    )
    parser.add_argument(
        "--db",
        default="jobs.db",
        help="path to SQLite database file (default: jobs.db)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    scrape = subparsers.add_parser("scrape", help="fetch jobs and save to DB")
    scrape.add_argument(
        "--category",
        choices=["graduate", "internship", "both"],
        default="both",
        help="which job category to scrape (default: both)",
    )
    scrape.set_defaults(func=cmd_scrape)

    list_cmd = subparsers.add_parser("list", help="show jobs from the DB")
    list_cmd.add_argument(
        "--limit",
        type=int,
        default=10,
        help="max jobs to show (default: 10)",
    )
    list_cmd.set_defaults(func=cmd_list)

    count = subparsers.add_parser("count", help="print number of jobs in the DB")
    count.set_defaults(func=cmd_count)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())