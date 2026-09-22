FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/api

# system deps (psycopg needs libpq at runtime via binary wheel; tesseract optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY apps/api ./

EXPOSE 8000

# The compose file overrides the command per service:
#   api:    alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
#   worker: python /srv/worker/scan_worker.py
COPY workers /srv/worker
COPY scripts /srv/scripts
