-- Migration 002: Add absolute closing timestamp to scraped_jobs
--
-- The `posted_date` column captures GradConnection's relative text
-- ("Closing in 4 days") at scrape time. That string drifts the moment
-- we render it later. To compute accurate countdowns on /browse, we
-- store the parsed deadline as an absolute TIMESTAMPTZ.
--
-- `posted_date` is kept around as the raw source text — useful for
-- debugging and "New!" banners that aren't expressible as a timestamp.
--
-- closing_at is NULL when GradConnection's text was unparseable
-- (e.g., "New!" or empty). The frontend falls back to posted_date in
-- those cases.

ALTER TABLE scraped_jobs
ADD COLUMN closing_at TIMESTAMPTZ NULL;

-- Index for fast "closing soon" sorts.
CREATE INDEX IF NOT EXISTS idx_scraped_jobs_closing_at
ON scraped_jobs (closing_at NULLS LAST);