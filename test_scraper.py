from src.job_scraper.scraper import Scraper

scraper = Scraper(category="both")
jobs = scraper.scrape()

print(f"\nGot {len(jobs)} jobs total\n")
for job in jobs[:3]:  # first 3 only
    print(f"- {job.title}")
    print(f"  {job.company} | {job.location}")
    print(f"  {job.url}")
    print(f"  {job.posted_date}")
    print(f"  {job.description[:80]}...")
    print()