# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (better layer caching)
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY . .

ENV AWAAZ_ROLE=api
EXPOSE 8000

# Healthcheck used by docker-compose
HEALTHCHECK --interval=10s --timeout=5s --retries=10 --start-period=20s \
    CMD curl --fail http://localhost:8000/healthz || exit 1

CMD ["python", "-m", "awaaz_api.main"]
