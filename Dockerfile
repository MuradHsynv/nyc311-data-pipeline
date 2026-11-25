# ---- Stage 1: builder. Installs dependencies into an isolated prefix ----
# Build tools and pip caches stay in this stage and never reach the final image.
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: runtime. Small image, no build tools, non-root user ----
FROM python:3.11-slim AS runtime

# PYTHONUNBUFFERED: logs appear immediately in `docker logs`
# PYTHONDONTWRITEBYTECODE: no .pyc files cluttering the container
# PYTHONPATH: lets `python -m pipeline.cli` find the package under /app/src
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src

# Run as an unprivileged user, never as root
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# Copy only the installed packages from the builder stage
COPY --from=builder /install /usr/local

# Application code and SQL migrations, owned by the unprivileged user
COPY --chown=app:app src ./src
COPY --chown=app:app migrations ./migrations

USER app

# Healthy means: the app imports and can reach the database
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 CMD python -c 'from pipeline.config import load_settings; from pipeline.db import get_connection; get_connection(load_settings(), max_wait_s=2).close()'

# Default command: one incremental run (compose overrides it for backfills and the scheduler)
CMD python -m pipeline.cli --mode incremental
