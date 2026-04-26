import sqlite3
from pathlib import Path

from .job import Job


class Database:
    def __init__(self, db_path: str = "jobs.db"):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # rows behave like dicts
        self._create_table()

    def _create_table(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                url TEXT NOT NULL UNIQUE,
                description TEXT,
                posted_date TEXT,
                source TEXT,
                scraped_at TEXT
            )
        """)
        self.conn.commit()

    def save_job(self, job: Job) -> bool:
        """Insert a job. Returns True if inserted, False if duplicate URL."""
        try:
            self.conn.execute(
                """
                INSERT INTO jobs
                    (title, company, location, url, description, posted_date, source, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.title, job.company, job.location, job.url,
                    job.description, job.posted_date, job.source,
                    job.scraped_at.isoformat(),
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # URL already exists

    def get_all_jobs(self) -> list[dict]:
        cursor = self.conn.execute("SELECT * FROM jobs ORDER BY scraped_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM jobs")
        return cursor.fetchone()[0]

    def close(self) -> None:
        self.conn.close()