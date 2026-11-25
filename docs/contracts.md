# Shared Project Contracts

This document is the single source of truth for shared interfaces across the team.
Do not change a contract alone: open a PR against `docs/contracts.md` and notify the team.

## 1. Environment Variables (`.env.example`)

```env
POSTGRES_USER=pipeline
POSTGRES_PASSWORD=change_me
POSTGRES_DB=nyc311
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

SOCRATA_APP_TOKEN=
SOCRATA_DATASET_ID=erm2-nwe9
SOCRATA_PAGE_SIZE=5000

QUALITY_FAIL_THRESHOLD=0.05
INITIAL_LOOKBACK_DAYS=30
SCHEDULE_CRON=0 3 * * *
LOG_LEVEL=INFO
```

Loaded into an immutable `Settings` dataclass (`src/pipeline/config.py`) via `load_settings()`:
- `db_host`, `db_port`, `db_user`, `db_password`, `db_name`
- `dataset_id`, `app_token`, `page_size`
- `threshold`, `lookback_days`, `schedule_cron`, `log_level`

## 2. Database Contract (`migrations/`)

Migrations are applied once each, in filename order, by `migrate.apply_migrations` and tracked in `ops.schema_migrations (filename, applied_at)`.

### `001_schemas_and_ops.sql` — Schemas & Operational Tables
- **Schemas:** `bronze`, `silver`, `gold`, `ops`
- **`ops.pipeline_runs`:**
  - `run_id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `mode TEXT NOT NULL CHECK (mode IN ('incremental', 'backfill'))`
  - `date_from DATE`, `date_to DATE`
  - `started_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `finished_at TIMESTAMPTZ`
  - `status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed'))`
  - `rows_ingested INTEGER NOT NULL DEFAULT 0`, `rows_quarantined INTEGER NOT NULL DEFAULT 0`, `rows_silver INTEGER NOT NULL DEFAULT 0`, `rows_gold INTEGER NOT NULL DEFAULT 0`
  - `error TEXT`
- **`ops.ingestion_state`:**
  - `source TEXT NOT NULL`, `window_key TEXT NOT NULL` (e.g. `'2025-01-01|2025-02-01'`)
  - `next_offset BIGINT NOT NULL DEFAULT 0`
  - `status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'complete'))`
  - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `PRIMARY KEY (source, window_key)`
- **`ops.quarantine`:**
  - `id BIGSERIAL PRIMARY KEY`
  - `run_id UUID NOT NULL`, `source_id TEXT NOT NULL`, `rule_name TEXT NOT NULL`, `reason TEXT NOT NULL`, `raw_record JSONB NOT NULL`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `UNIQUE (source_id, rule_name)`

### `002_bronze_silver.sql` — Bronze & Silver Tables
- **`bronze.requests_raw`:**
  - `source_id TEXT PRIMARY KEY` (API `unique_key`)
  - `source_created_at TIMESTAMP`
  - `payload JSONB NOT NULL`
  - `run_id UUID NOT NULL`
  - `ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- **`silver.service_requests`:**
  - `unique_key TEXT PRIMARY KEY`
  - `created_date TIMESTAMP NOT NULL`, `closed_date TIMESTAMP`
  - `agency TEXT NOT NULL`, `agency_name TEXT`
  - `complaint_type TEXT NOT NULL`, `descriptor TEXT`
  - `status TEXT NOT NULL`
  - `borough TEXT`, `city TEXT`, `incident_zip TEXT`
  - `latitude DOUBLE PRECISION`, `longitude DOUBLE PRECISION`
  - `open_data_channel_type TEXT`
  - `bronze_run_id UUID NOT NULL`
  - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

### `003_gold.sql` — Gold Star Schema
- **`gold.dim_date`:** `(date_key INTEGER PRIMARY KEY, full_date DATE NOT NULL UNIQUE, year SMALLINT, quarter SMALLINT, month SMALLINT, month_name TEXT, day SMALLINT, day_of_week SMALLINT, day_name TEXT, is_weekend BOOLEAN)`
- **`gold.dim_agency` (SCD Type 2):** `(agency_sk BIGSERIAL PRIMARY KEY, agency_code TEXT NOT NULL, agency_name TEXT, row_hash TEXT NOT NULL, valid_from TIMESTAMP NOT NULL, valid_to TIMESTAMP, is_current BOOLEAN NOT NULL DEFAULT TRUE)` with partial unique index `UNIQUE (agency_code) WHERE is_current`
- **`gold.dim_location`:** `(location_sk BIGSERIAL PRIMARY KEY, borough TEXT NOT NULL, city TEXT NOT NULL, incident_zip TEXT NOT NULL, UNIQUE (borough, city, incident_zip))`
- **`gold.dim_complaint_type`:** `(complaint_type_sk BIGSERIAL PRIMARY KEY, complaint_type TEXT NOT NULL, descriptor TEXT NOT NULL, UNIQUE (complaint_type, descriptor))`
- **`gold.fact_service_requests`:** `(unique_key TEXT PRIMARY KEY, created_date_key INTEGER NOT NULL REFERENCES gold.dim_date(date_key), closed_date_key INTEGER REFERENCES gold.dim_date(date_key), created_at TIMESTAMP NOT NULL, closed_at TIMESTAMP, agency_sk BIGINT NOT NULL REFERENCES gold.dim_agency(agency_sk), complaint_type_sk BIGINT NOT NULL REFERENCES gold.dim_complaint_type(complaint_type_sk), location_sk BIGINT NOT NULL REFERENCES gold.dim_location(location_sk), status TEXT NOT NULL, resolution_hours NUMERIC(12, 2), latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, load_run_id UUID NOT NULL)`

### `004_indexes.sql` — Performance Indexes
- `idx_fact_created_date_key` on `gold.fact_service_requests (created_date_key)`
- `idx_fact_status_created` on `gold.fact_service_requests (status, created_at)`
- `idx_fact_agency_complaint` on `gold.fact_service_requests (agency_sk, complaint_type_sk)`
- `idx_fact_agency_created` on `gold.fact_service_requests (agency_sk, created_at DESC)`

## 3. Python Module Interface (`src/pipeline/`)

| Module | Function or class | Owner |
|---|---|---|
| `config.py` | `Settings` dataclass and `load_settings() -> Settings` reading the env vars above | #3 |
| `db.py` | `get_connection(settings, max_wait_s=60) -> psycopg2 connection` (retries until the DB is ready) | #3 |
| `runs.py` | `start_run(conn, mode, date_from, date_to) -> run_id (str)`, `finish_run(conn, run_id, status, counts: dict, error: str \| None)`, `mark_stale_runs(conn) -> int`, and `count_quarantined(conn, run_id) -> int` | #3 |
| `pipeline.py` | `run_pipeline(settings, mode, date_from=None, date_to=None) -> str \| None` orchestrates everything under advisory lock `727312` | #3 |
| `cli.py` | `python -m pipeline.cli --mode incremental` or `--mode backfill --from YYYY-MM-DD --to YYYY-MM-DD` | #3 |
| `scheduler.py` | APScheduler `BlockingScheduler` running incremental mode on `SCHEDULE_CRON` | #3 |
| `migrate.py` | `apply_migrations(conn, migrations_dir='migrations') -> list[str]` | #2 |
| `bulk.py` | `upsert_via_copy(conn, table, columns, rows, conflict_cols, update_cols=None) -> int` | #2 |
| `gold.py` | `load_gold(conn, run_id) -> int` (returns fact rows touched) | #2 |
| `api_client.py` | `SocrataClient(dataset_id, app_token, page_size)` with `fetch_page(offset, where)` and `iter_pages(where, start_offset)` | #1 |
| `schema_check.py` | `check_schema(rows) -> list[str]` (warnings), raises `SchemaDriftError` on breaking change | #1 |
| `ingest.py` | `resolve_window(conn, mode, date_from, date_to, settings) -> (date_from, date_to)` and `ingest_window(conn, client, run_id, date_from, date_to) -> int` | #1 |
| `validate.py` | `validate_record(raw: dict) -> list[Violation]` (empty list means valid) | #1 |
| `silver.py` | `build_silver(silver_conn, quarantine_conn, run_id, threshold) -> SilverResult`, raises `QualityGateError` | #1 |

## 4. Run Lifecycle (`pipeline.py`)

```python
def run_pipeline(settings, mode, date_from=None, date_to=None):
    conn = get_connection(settings)
    # Acquire session advisory lock 727312 (pg_try_advisory_lock)
    apply_migrations(conn)
    mark_stale_runs(conn)
    date_from, date_to = resolve_window(conn, mode, date_from, date_to, settings)
    run_id = start_run(conn, mode, date_from, date_to)
    counts = {}
    try:
        client = SocrataClient(settings.dataset_id, settings.app_token, settings.page_size)
        counts["rows_ingested"] = ingest_window(conn, client, run_id, date_from, date_to)
        # Two connections: silver work can be rolled back while quarantine is kept
        silver_conn = get_connection(settings)
        quarantine_conn = get_connection(settings)
        result = build_silver(silver_conn, quarantine_conn, run_id, settings.threshold)
        counts["rows_silver"] = result.valid
        counts["rows_quarantined"] = result.invalid
        counts["rows_gold"] = load_gold(conn, run_id)
        finish_run(conn, run_id, "success", counts, None)
        return run_id
    except Exception as exc:
        conn.rollback()
        counts.setdefault("rows_quarantined", count_quarantined(conn, run_id))
        finish_run(conn, run_id, "failed", counts, type(exc).__name__ + ": " + str(exc))
        raise
```

## 5. Dataset Facts and Gotchas

- **Endpoint:** `https://data.cityofnewyork.us/resource/erm2-nwe9.json`
- **Pagination:** `$limit`, `$offset`, with stable `$order=created_date, unique_key`. - **Window filter:** `$where=created_date >= '2025-01-01T00:00:00' AND created_date < '2025-02-01T00:00:00'` (upper bound exclusive).
- **Timestamps:** Floating timestamps without timezone (e.g. `2025-01-02T10:00:00.000`), stored as `TIMESTAMP`.
- **Omitted null fields:** Socrata omits null attributes from individual JSON objects; always access optional keys via `.get()`.
