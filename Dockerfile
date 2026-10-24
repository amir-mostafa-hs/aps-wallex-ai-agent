# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    DASHBOARD_BIND=0.0.0.0 \
    DASHBOARD_PORT=8000 \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# Create non-root user
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -m -s /bin/bash appuser

# Install python dependencies with increased timeout for network stability
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=120 -r requirements.txt

# Create runtime directories with proper permissions for SQLite & logs
RUN mkdir -p /app/data /app/logs && \
    chown -R appuser:appgroup /app/data /app/logs /app

# Copy application source, sources data, and tests
COPY --chown=appuser:appgroup src/ /app/src/
COPY --chown=appuser:appgroup docs/sources/ /app/docs/sources/
COPY --chown=appuser:appgroup tests/ /app/tests/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1

CMD ["python", "-m", "wallex_agent", "shadow"]
