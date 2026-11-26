import os

import pytest

from pipeline.config import load_settings
from pipeline.db import get_connection
from pipeline.migrate import apply_migrations

TABLES = (
    "bronze.requests_raw, silver.service_requests, ops.quarantine, "
    "ops.ingestion_state, ops.pipeline_runs, gold.fact_service_requests, "
    "gold.dim_agency, gold.dim_location, gold.dim_complaint_type, gold.dim_date"
)


@pytest.fixture
def settings():
    s = load_settings()
    # These fixtures TRUNCATE every table, so refuse to run against a real database.
    # GitHub Actions sets CI=true, and its throwaway database is called nyc311.
    if not s.db_name.endswith("_test") and not os.getenv("CI"):
        pytest.exit(
            f"Refusing to truncate '{s.db_name}'. Use POSTGRES_DB=nyc311_test.", returncode=2
        )
    return s


@pytest.fixture
def db_conn(settings):
    """A connection to a migrated, empty database used by integration tests."""
    conn = get_connection(settings, max_wait_s=30)
    apply_migrations(conn, "migrations")
    with conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE " + TABLES + " RESTART IDENTITY CASCADE")
    yield conn
    conn.close()
