"""Resumable Bronze ingestion: Socrata API -> bronze.requests_raw + checkpoints."""

import json
import logging
from datetime import datetime

from pipeline.bulk import upsert_via_copy
from pipeline.schema_check import check_schema

log = logging.getLogger(__name__)

BRONZE_COLUMNS = ["source_id", "source_created_at", "payload", "run_id"]


def _iso_date(value):
    """Normalize a date/datetime or YYYY-MM-DD string to 'YYYY-MM-DD'."""
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value).strip()[:10]


def _parse_created_at(value):
    """Parse an ISO timestamp string for source_created_at, or None if malformed."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip()).replace(tzinfo=None)
    except ValueError:
        return None
    return dt.isoformat()


def _prepare_bronze_rows(rows, run_id):
    """Convert raw API dicts into deduplicated tuples for bronze.requests_raw."""
    by_id = {}
    run_id_str = str(run_id)
    for record in rows:
        source_id = str(record.get("unique_key") or "").strip()
        if not source_id:
            log.warning("skipping record with missing unique_key")
            continue
        by_id[source_id] = (
            source_id,
            _parse_created_at(record.get("created_date")),
            json.dumps(record),
            run_id_str,
        )
    return list(by_id.values())


def _get_or_init_checkpoint(conn, source, window_key):
    """Return (next_offset, status) for a (source, window_key) checkpoint."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ops.ingestion_state (source, window_key, next_offset, status)
            VALUES (%s, %s, 0, 'in_progress')
            ON CONFLICT (source, window_key) DO NOTHING
            """,
            (source, window_key),
        )
        cur.execute(
            """
            SELECT next_offset, status
            FROM ops.ingestion_state
            WHERE source = %s AND window_key = %s
            """,
            (source, window_key),
        )
        next_offset, status = cur.fetchone()
    conn.commit()
    return next_offset, status


def get_watermark(conn):
    """Return the latest source_created_at in bronze.requests_raw, or None if empty."""
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(source_created_at) FROM bronze.requests_raw")
        return cur.fetchone()[0]


def ingest_window(conn, client, date_from, date_to, run_id, source="nyc311", force=False):
    """Ingest one [date_from, date_to) window into bronze.requests_raw resumptively.

    Commits each page together with its ops.ingestion_state offset so a crash
    mid-window resumes cleanly from the last committed offset.
    Returns total rows written during this call.
    """
    start_str = _iso_date(date_from)
    end_str = _iso_date(date_to)
    window_key = f"{start_str}|{end_str}"

    start_offset, status = _get_or_init_checkpoint(conn, source, window_key)
    if status == "complete" and not force:
        log.info("window %s already complete, skipping", window_key)
        return 0

    if force:
        start_offset = 0

    where = f"created_date >= '{start_str}T00:00:00' AND created_date < '{end_str}T00:00:00'"

    total_written = 0
    for rows, next_offset in client.iter_pages(where=where, start_offset=start_offset):
        # Fail loudly on missing core columns; log non-fatal warnings for new ones.
        for warning in check_schema(rows):
            log.warning("schema drift warning (%s): %s", window_key, warning)

        bronze_rows = _prepare_bronze_rows(rows, run_id)
        written = upsert_via_copy(
            conn,
            "bronze.requests_raw",
            BRONZE_COLUMNS,
            bronze_rows,
            conflict_cols=["source_id"],
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ops.ingestion_state
                SET next_offset = %s, status = 'in_progress', updated_at = now()
                WHERE source = %s AND window_key = %s
                """,
                (next_offset, source, window_key),
            )
        # Single commit keeps Bronze data and the checkpoint strictly in sync.
        conn.commit()
        total_written += written
        log.info(
            "window %s: upserted %d rows (next_offset=%d)",
            window_key,
            written,
            next_offset,
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ops.ingestion_state
            SET status = 'complete', updated_at = now()
            WHERE source = %s AND window_key = %s
            """,
            (source, window_key),
        )
    conn.commit()
    log.info("window %s complete: %d rows ingested", window_key, total_written)
    return total_written
