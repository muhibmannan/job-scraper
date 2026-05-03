from dotenv import load_dotenv

load_dotenv()

from datetime import datetime
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .database import Database
from .scraper import Scraper

from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

DB_PATH = "jobs.db"

import os

SCRAPE_INTERVAL_MINUTES = int(os.environ.get("SCRAPE_INTERVAL_MINUTES", "30"))

def _scheduled_scrape() -> None:
    """The function the scheduler calls. Same shape as _run_scrape but always 'both'."""
    print("[scheduler] starting scrape...")
    scraper = Scraper(category="both")
    db = Database(DB_PATH)
    try:
        jobs = scraper.scrape()
        inserted = sum(1 for job in jobs if db.save_job(job))
        print(f"[scheduler] {inserted} new, {len(jobs) - inserted} duplicates")
    except Exception as e:
        print(f"[scheduler] failed: {e}")
    finally:
        db.close()

def _is_paused() -> bool:
    """Return True if the scheduler is paused (not the same as 'not running')."""
    return scheduler.state == 2  # APScheduler STATE_PAUSED constant


scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler.add_job(
        _scheduled_scrape,
        trigger=IntervalTrigger(minutes=SCRAPE_INTERVAL_MINUTES),
        id="periodic_scrape",
        name="GradConnection periodic scrape",
        replace_existing=True,
    )
    scheduler.start()
    print(f"[scheduler] started, scraping every {SCRAPE_INTERVAL_MINUTES} minutes")
    yield                              # ← THIS LINE IS MISSING
    # Shutdown
    scheduler.shutdown(wait=False)
    print("[scheduler] stopped")


app = FastAPI(
    title="Job Scraper API",
    description="HTTP interface for the GradConnection job scraper.",
    version="0.7.0",
    lifespan=lifespan,
)


# ----- Pydantic models -----

class JobResponse(BaseModel):
    """A single job as returned by the API."""

    id: int = Field(..., description="Database row id", examples=[42])
    title: str = Field(..., description="Job title", examples=["Graduate Software Developer: 2027"])
    company: str = Field(..., description="Hiring company", examples=["Susquehanna International Group"])
    location: str = Field(..., description="Job location", examples=["Sydney"])
    url: str = Field(..., description="Original posting URL")
    description: str = Field("", description="Short job description from listing card")
    posted_date: str = Field("", description="Closing/posted info as scraped (e.g. 'Closing in 13 days')")
    source: str = Field(..., description="Source identifier, e.g. 'gradconnection-graduate'")
    scraped_at: datetime = Field(..., description="When this row was inserted into the DB")


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["healthy"])


class RootResponse(BaseModel):
    status: str
    message: str


class ScrapeRequest(BaseModel):
    category: str = Field(
        "both",
        description="Which jobs to scrape: 'graduate', 'internship', or 'both'.",
        examples=["both"],
    )

class ScrapeResponse(BaseModel):
    status: str = Field(..., examples=["queued"])
    category: str = Field(..., examples=["both"])
    message: str

class SchedulerJobResponse(BaseModel):
    id: str = Field(..., examples=["periodic_scrape"])
    name: str = Field(..., examples=["GradConnection periodic scrape"])
    trigger: str = Field(..., description="Human-readable trigger description", examples=["interval[0:30:00]"])
    next_run_time: datetime | None = Field(None, description="When the job will next fire, or null if paused")


class SchedulerStatusResponse(BaseModel):
    running: bool
    paused: bool
    jobs: list[SchedulerJobResponse]


# ----- Helpers -----

def _run_scrape(category: str) -> None:
    """Background task: run a scrape and save results."""
    scraper = Scraper(category=category)
    db = Database(DB_PATH)
    try:
        jobs = scraper.scrape()
        inserted = sum(1 for job in jobs if db.save_job(job))
        print(f"[background scrape] {inserted} new, {len(jobs) - inserted} duplicates")
    except Exception as e:
        print(f"[background scrape] failed: {e}")
    finally:
        db.close()


# ----- Routes: meta -----

@app.get("/", response_model=RootResponse, tags=["meta"])
def root() -> RootResponse:
    return RootResponse(status="ok", message="Job Scraper API is running")


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    return HealthResponse(status="healthy")


# ----- Routes: jobs -----

@app.get("/jobs", response_model=list[JobResponse], tags=["jobs"])
def list_jobs(
    category: Annotated[
        str | None,
        Query(
            description="Filter by category: 'graduate' or 'internship'.",
            examples=["graduate"],
        ),
    ] = None,
    company: Annotated[
        str | None,
        Query(
            description="Case-insensitive substring match on company name.",
            examples=["tiktok"],
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=200,
            description="Maximum number of jobs to return (1-200).",
        ),
    ] = 50,
) -> list[JobResponse]:
    """Return jobs from the database, optionally filtered by category or company."""
    db = Database(DB_PATH)
    try:
        rows = db.search_jobs(category=category, company=company, limit=limit)
        return [JobResponse(**row) for row in rows]
    finally:
        db.close()


@app.get("/jobs/{job_id}", response_model=JobResponse, tags=["jobs"])
def get_job(job_id: int) -> JobResponse:
    """Fetch a single job by its database id. Returns 404 if not found."""
    db = Database(DB_PATH)
    try:
        row = db.get_job(job_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return JobResponse(**row)
    finally:
        db.close()

class CompanyCount(BaseModel):
    company: str
    count: int


class StatsResponse(BaseModel):
    total: int = Field(..., description="Total jobs in the database", examples=[40])
    by_source: dict[str, int] = Field(
        ...,
        description="Count grouped by source identifier",
        examples=[{"gradconnection-graduate": 20, "gradconnection-internship": 20}],
    )
    top_companies: list[CompanyCount] = Field(
        ...,
        description="Top 10 hiring companies, descending by count",
    )


@app.post("/scrape", response_model=ScrapeResponse, status_code=202, tags=["jobs"])
def trigger_scrape(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
) -> ScrapeResponse:
    """Trigger an async scrape. Returns immediately; scrape runs in the background."""
    valid = {"graduate", "internship", "both"}
    if request.category not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"category must be one of {sorted(valid)}, got {request.category!r}",
        )
    background_tasks.add_task(_run_scrape, request.category)
    return ScrapeResponse(
        status="queued",
        category=request.category,
        message="Scrape started in background. Poll /jobs to see new entries.",
    )

@app.get("/stats", response_model=StatsResponse, tags=["meta"])
def get_stats() -> StatsResponse:
    """Aggregate stats: total job count, breakdown by source, and top companies."""
    db = Database(DB_PATH)
    try:
        return StatsResponse(**db.stats())
    finally:
        db.close()

# ----- Routes: scheduler -----

@app.get(
    "/scheduler/jobs",
    response_model=SchedulerStatusResponse,
    tags=["scheduler"],
)
def scheduler_status() -> SchedulerStatusResponse:
    """Inspect scheduled jobs: ids, triggers, and next fire times."""
    jobs = [
        SchedulerJobResponse(
            id=job.id,
            name=job.name,
            trigger=str(job.trigger),
            next_run_time=job.next_run_time,
        )
        for job in scheduler.get_jobs()
    ]
    return SchedulerStatusResponse(
        running=scheduler.running,
        paused=_is_paused(),
        jobs=jobs,
    )


@app.post("/scheduler/pause", tags=["scheduler"], status_code=200)
def scheduler_pause() -> dict[str, str]:
    """Pause all scheduled jobs. Existing in-flight runs finish; no new ones fire."""
    if _is_paused():
        return {"status": "already_paused"}
    scheduler.pause()
    return {"status": "paused"}


@app.post("/scheduler/resume", tags=["scheduler"], status_code=200)
def scheduler_resume() -> dict[str, str]:
    """Resume scheduled jobs."""
    if not _is_paused():
        return {"status": "already_running"}
    scheduler.resume()
    return {"status": "resumed"}