"""Resumable ingestion of one date window into bronze."""

import hashlib
import json
import logging
from datetime import date, datetime, timedelta

from psycopg2.extras import Json, execute_values

from pipeline.schema_check import check_schema

log = logging.getLogger(__name__)
SOURCE = "nyc311"


def _ts(d):
    """Format a date as the floating timestamp string Socrata expects."""
    return d.strftime("%Y-%m-%dT00:00:00")


def build_where(date_from, date_to):
    """SoQL filter for the window. Upper bound is exclusive."""
    return f"created_date >= '{_ts(date_from)}' AND created_date < '{_ts(date_to)}'"


def resolve_window(conn, mode, date_from, date_to, settings):
    """Decide which date window this run should ingest."""
    if mode == "backfill":
        if not (date_from and date_to):
            raise ValueError("backfill needs both --from and --to")
        return date_from, date_to

    # Incremental: start 1 day before the newest row we already have (overlap is safe
    # because loads are idempotent) and run up to tomorrow.
    with conn.cursor() as cur:
        cur.execute("SELECT max(source_created_at) FROM bronze.requests_raw")
        latest = cur.fetchone()[0]
    conn.commit()  # do not leave the connection idle inside a transaction

    tomorrow = date.today() + timedelta(days=1)
    if latest is None:
        start = date.today() - timedelta(days=settings.lookback_days)
    else:
        start = latest.date() - timedelta(days=1)
    return start, tomorrow


def _source_id(record):
    """Use API unique_key; if missing, derive a stable hash so it still reaches quarantine."""
    key = record.get("unique_key")
    if key:
        return str(key)
    digest = hashlib.sha1(json.dumps(record, sort_keys=True).encode()).hexdigest()
    return "missing-" + digest[:16]


def _created_at(record):
    """Parse created_date for the bronze helper column; None if absent or malformed."""
    try:
        return datetime.fromisoformat(record["created_date"]).replace(tzinfo=None)
    except (KeyError, ValueError, TypeError):
        return None


def _start_or_resume(conn, window_key):
    """Return the offset to start from.

    No state yet: start at 0.
    State is in_progress: a previous run died mid-window, so RESUME from next_offset.
    State is complete: the window was fully loaded before; restart at 0 to refresh it.
    """
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ops.ingestion_state (source, window_key)
                VALUES (%s, %s)
                ON CONFLICT (source, window_key) DO NOTHING
                """,
                (SOURCE, window_key),
            )
            cur.execute(
                """
                SELECT next_offset, status
                FROM ops.ingestion_state
                WHERE source = %s AND window_key = %s
                FOR UPDATE
                """,
                (SOURCE, window_key),
            )
            offset, status = cur.fetchone()
            if status == "complete":
                cur.execute(
                    """
                    UPDATE ops.ingestion_state
                    SET next_offset = 0, status = 'in_progress', updated_at = now()
                    WHERE source = %s AND window_key = %s
                    """,
                    (SOURCE, window_key),
                )
                return 0
            return offset


def _load_batch(conn, run_id, window_key, rows, next_offset):
    """Upsert one page into bronze AND advance the checkpoint in a single transaction."""
    # De-duplicate inside the page: one INSERT cannot touch the same key twice.
    unique = {}
    for record in rows:
        unique[_source_id(record)] = record

    values = [(sid, _created_at(rec), Json(rec), run_id) for sid, rec in unique.items()]
    with conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO bronze.requests_raw
                    (source_id, source_created_at, payload, run_id)
                VALUES %s
                ON CONFLICT (source_id) DO UPDATE SET
                    source_created_at = EXCLUDED.source_created_at,
                    payload = EXCLUDED.payload,
                    run_id = EXCLUDED.run_id,
                    ingested_at = now()
                """,
                values,
                page_size=1000,
            )
            cur.execute(
                """
                UPDATE ops.ingestion_state
                SET next_offset = %s, updated_at = now()
                WHERE source = %s AND window_key = %s
                """,
                (next_offset, SOURCE, window_key),
            )


def _adopt_interrupted_rows(conn, run_id, date_from, date_to):
    """Re-tag bronze rows written by earlier FAILED runs of the same window with this run_id.

    Without this, a resumed run would only validate rows fetched after the crash,
    leaving pre-crash rows out of silver and gold.
    """
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE bronze.requests_raw
                SET run_id = %s
                WHERE run_id IN (
                    SELECT run_id
                    FROM ops.pipeline_runs
                    WHERE status = 'failed'
                      AND date_from = %s
                      AND date_to = %s
                      AND run_id <> %s
                )
                """,
                (run_id, date_from, date_to, run_id),
            )


def ingest_window(conn, client, run_id, date_from, date_to):
    """Ingest [date_from, date_to) into bronze. Returns rows loaded by THIS invocation."""
    window_key = date_from.isoformat() + "|" + date_to.isoformat()
    where = build_where(date_from, date_to)
    offset = _start_or_resume(conn, window_key)
    log.info("ingesting %s starting at offset %s", window_key, offset)

    if offset > 0:
        # Resumed after a crash: pull earlier rows from this window into this run_id
        # so silver and gold (which read WHERE run_id = this run) process the full window.
        _adopt_interrupted_rows(conn, run_id, date_from, date_to)

    total = 0
    for rows, next_offset in client.iter_pages(where, offset):
        for warning in check_schema(rows):
            log.warning(warning)
        _load_batch(conn, run_id, window_key, rows, next_offset)
        total += len(rows)
        log.info("loaded %s rows (offset now %s)", total, next_offset)

    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ops.ingestion_state
                SET status = 'complete', updated_at = now()
                WHERE source = %s AND window_key = %s
                """,
                (SOURCE, window_key),
            )
    return total
