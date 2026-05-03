import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .job import Job


class Database:
    """Postgres-backed storage for scraped jobs.

    Connection details come from the DATABASE_URL environment variable.
    Each instance opens one connection; call .close() when finished.
    """

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.environ.get("DATABASE_URL")
        if not self.dsn:
            raise RuntimeError(
                "DATABASE_URL is not set. Add it to your .env file or environment."
            )
        self.conn = psycopg.connect(self.dsn, row_factory=dict_row, autocommit=True)

    @contextmanager
    def _cursor(self):
        cur = self.conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    def save_job(self, job: Job) -> bool:
        """Insert a job. Returns True if inserted, False if a row with this URL exists."""
        try:
            with self._cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scraped_jobs
                        (title, company, location, url, description, posted_date, source, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        job.title,
                        job.company,
                        job.location,
                        job.url,
                        job.description,
                        job.posted_date,
                        job.source,
                        job.scraped_at,
                    ),
                )
            return True
        except psycopg.errors.UniqueViolation:
            return False  # URL already exists

    def get_all_jobs(self) -> list[dict]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM scraped_jobs ORDER BY scraped_at DESC")
            return cur.fetchall()

    def search_jobs(
        self,
        category: str | None = None,
        company: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        clauses = []
        params: list = []

        if category is not None:
            clauses.append("source LIKE %s")
            params.append(f"%-{category}")

        if company is not None:
            clauses.append("LOWER(company) LIKE %s")
            params.append(f"%{company.lower()}%")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM scraped_jobs {where} ORDER BY scraped_at DESC LIMIT %s"
        params.append(limit)

        with self._cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def get_job(self, job_id: int) -> dict | None:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM scraped_jobs WHERE id = %s", (job_id,))
            return cur.fetchone()

    def count(self) -> int:
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM scraped_jobs")
            row = cur.fetchone()
            return row["c"] if row else 0

    def stats(self) -> dict:
        total = self.count()

        with self._cursor() as cur:
            cur.execute(
                "SELECT source, COUNT(*) AS count "
                "FROM scraped_jobs GROUP BY source ORDER BY count DESC"
            )
            by_source = {row["source"]: row["count"] for row in cur.fetchall()}

        with self._cursor() as cur:
            cur.execute(
                "SELECT company, COUNT(*) AS count "
                "FROM scraped_jobs GROUP BY company ORDER BY count DESC LIMIT 10"
            )
            top_companies = [
                {"company": row["company"], "count": row["count"]}
                for row in cur.fetchall()
            ]

        return {
            "total": total,
            "by_source": by_source,
            "top_companies": top_companies,
        }

    def close(self) -> None:
        self.conn.close()