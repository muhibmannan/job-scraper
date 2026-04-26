from src.job_scraper.job import Job
from src.job_scraper.database import Database

db = Database("jobs.db")

fake = Job(
    title="Graduate Software Engineer",
    company="Test Co",
    location="Sydney",
    url="https://example.com/jobs/1",
)

print(f"Insert 1: {db.save_job(fake)}")        # True
print(f"Insert 2 (dupe): {db.save_job(fake)}") # False
print(f"Total: {db.count()}")                  # 1
print(f"Rows:  {db.get_all_jobs()}")

db.close()