"""Integration test fixtures for the gold layer.

Temporary local db_conn fixture so the gold tests can run before #3's tests/conftest.py
(with config.py and db.py) lands. Once that file is merged, this one can be deleted.
"""

import os

import psycopg2
import pytest

from pipeline.migrate import apply_migrations

TABLES = (
    "bronze.requests_raw, silver.service_requests, ops.quarantine, ops.ingestion_state, "
    "ops.pipeline_runs, gold.fact_service_requests, gold.dim_agency, gold.dim_location, "
    "gold.dim_complaint_type, gold.dim_date"
)


@pytest.fixture
def db_conn():
    """A connection to a migrated, EMPTY database. Reads POSTGRES_* like CI does."""
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "pipeline"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        dbname=os.getenv("POSTGRES_DB", "nyc311"),
    )
    apply_migrations(conn, "migrations")
    with conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE " + TABLES + " RESTART IDENTITY CASCADE")
    yield conn
    conn.close()
