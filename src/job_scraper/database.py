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
    
    def search_jobs(
        self,
        category: str | None = None,
        company: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search jobs with optional filters. Returns most recently scraped first."""
        clauses = []
        params: list = []

        if category is not None:
            # source values look like 'gradconnection-graduate' or 'gradconnection-internship'
            clauses.append("source LIKE ?")
            params.append(f"%-{category}")

        if company is not None:
            clauses.append("LOWER(company) LIKE ?")
            params.append(f"%{company.lower()}%")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM jobs {where} ORDER BY scraped_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_job(self, job_id: int) -> dict | None:
        """Fetch a single job by id. Returns None if not found."""
        cursor = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def stats(self) -> dict:
        """Return aggregate stats: total count, breakdowns by source and company."""
        total = self.count()

        cursor = self.conn.execute(
            "SELECT source, COUNT(*) as count FROM jobs GROUP BY source ORDER BY count DESC"
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        cursor = self.conn.execute(
            "SELECT company, COUNT(*) as count FROM jobs "
            "GROUP BY company ORDER BY count DESC LIMIT 10"
        )
        top_companies = [
            {"company": row["company"], "count": row["count"]}
            for row in cursor.fetchall()
        ]

        return {
            "total": total,
            "by_source": by_source,
            "top_companies": top_companies,
        }

    def count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM jobs")
        return cursor.fetchone()[0]

    def close(self) -> None:
        self.conn.close()