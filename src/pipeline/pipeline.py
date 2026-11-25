"""Orchestrates one end-to-end pipeline run: ingest, validate, silver, gold, and run tracking."""

import logging

from pipeline.api_client import SocrataClient
from pipeline.db import get_connection
from pipeline.gold import load_gold
from pipeline.ingest import ingest_window, resolve_window
from pipeline.migrate import apply_migrations
from pipeline.runs import count_quarantined, finish_run, mark_stale_runs, start_run
from pipeline.silver import build_silver

log = logging.getLogger(__name__)

# Session-level advisory lock ID so at most one pipeline run executes at a time.
RUN_LOCK_ID = 727312


def run_pipeline(settings, mode, date_from=None, date_to=None):
    """Execute one pipeline run. Returns run_id, or None if another run holds the lock."""
    conn = get_connection(settings)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (RUN_LOCK_ID,))
            got_lock = cur.fetchone()[0]
        conn.commit()
        if not got_lock:
            log.warning("another run is in progress, skipping")
            return None

        apply_migrations(conn)
        mark_stale_runs(conn)

        date_from, date_to = resolve_window(conn, mode, date_from, date_to, settings)
        run_id = start_run(conn, mode, date_from, date_to)
        log.info("run %s started: mode=%s window=%s..%s", run_id, mode, date_from, date_to)

        counts = {}
        silver_conn = None
        quarantine_conn = None
        try:
            client = SocrataClient(settings.dataset_id, settings.app_token, settings.page_size)
            counts["rows_ingested"] = ingest_window(conn, client, run_id, date_from, date_to)

            # Separate connections so silver can roll back on QualityGateError
            # while quarantine rows stay committed for debugging.
            silver_conn = get_connection(settings)
            quarantine_conn = get_connection(settings)
            result = build_silver(silver_conn, quarantine_conn, run_id, settings.threshold)
            counts["rows_silver"] = result.valid
            counts["rows_quarantined"] = result.invalid

            counts["rows_gold"] = load_gold(conn, run_id)
            finish_run(conn, run_id, "success", counts, None)
            log.info("run %s succeeded: %s", run_id, counts)
            return run_id
        except Exception as exc:
            conn.rollback()
            counts.setdefault("rows_quarantined", count_quarantined(conn, run_id))
            finish_run(conn, run_id, "failed", counts, f"{type(exc).__name__}: {exc}")
            log.exception("run %s failed", run_id)
            raise
        finally:
            for extra in (silver_conn, quarantine_conn):
                if extra is not None:
                    extra.close()
    finally:
        # Closing the session connection automatically releases the advisory lock.
        conn.close()
