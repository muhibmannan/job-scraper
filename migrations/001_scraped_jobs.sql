-- Phase 4.1: scraped_jobs table

CREATE TABLE IF NOT EXISTS scraped_jobs (
    id          BIGSERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    company     TEXT NOT NULL,
    location    TEXT,
    url         TEXT NOT NULL UNIQUE,
    description TEXT,
    posted_date TEXT,
    source      TEXT NOT NULL,
    scraped_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS scraped_jobs_source_idx     ON scraped_jobs (source);
CREATE INDEX IF NOT EXISTS scraped_jobs_company_idx    ON scraped_jobs (lower(company));
CREATE INDEX IF NOT EXISTS scraped_jobs_scraped_at_idx ON scraped_jobs (scraped_at DESC);

ALTER TABLE scraped_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "scraped_jobs are publicly readable" ON scraped_jobs;
CREATE POLICY "scraped_jobs are publicly readable"
  ON scraped_jobs
  FOR SELECT
  USING (true);