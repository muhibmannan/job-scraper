# Phase 4.2: container for FastAPI + APScheduler

FROM python:3.12-slim

# System packages: lxml needs libxml2 + libxslt at runtime, psycopg builds wheels for libpq
# We use the [binary] extras of psycopg so we don't need libpq-dev — just the runtime libs.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libxml2 libxslt1.1 \
 && rm -rf /var/lib/apt/lists/*

# All app code lives under /app inside the container
WORKDIR /app

# Copy requirements first so Docker can cache the pip install layer.
# If only source code changes (not dependencies), rebuilds skip pip install entirely.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Tell Fly which port the app listens on (we'll match this in fly.toml)
EXPOSE 8000

# Bind to 0.0.0.0 so the container accepts connections from outside, not just localhost
CMD ["uvicorn", "src.job_scraper.api:app", "--host", "0.0.0.0", "--port", "8000"]