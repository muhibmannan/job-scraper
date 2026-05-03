from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .database import Database

app = FastAPI(
    title="Job Scraper API",
    description="HTTP interface for the GradConnection job scraper.",
    version="0.2.0",
)

DB_PATH = "jobs.db"


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


@app.get("/", response_model=RootResponse, tags=["meta"])
def root() -> RootResponse:
    return RootResponse(status="ok", message="Job Scraper API is running")


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@app.get("/jobs", response_model=list[JobResponse], tags=["jobs"])
def list_jobs() -> list[JobResponse]:
    """Return all jobs stored in the database."""
    db = Database(DB_PATH)
    try:
        rows = db.get_all_jobs()
        return [JobResponse(**row) for row in rows]
    finally:
        db.close()