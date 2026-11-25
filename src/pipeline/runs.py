"""Run history: one row per pipeline run in ops.pipeline_runs."""


def start_run(conn, mode, date_from, date_to):
    """Insert a row with status 'running' and return its run_id as a string.

    The database generates the UUID (gen_random_uuid default in migration 001), and
    RETURNING hands it back in the same round trip.
    """
    with conn:  # commits on success, rolls back on error
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ops.pipeline_runs (mode, date_from, date_to)
                   VALUES (%s, %s, %s) RETURNING run_id""",
                (mode, date_from, date_to),
            )
            return str(cur.fetchone()[0])


def finish_run(conn, run_id, status, counts, error):
    """Close the run with its final status, row counts and error text (None on success).

    counts is a dict with optional keys rows_ingested, rows_quarantined, rows_silver and
    rows_gold. Missing keys become 0, so a run that failed early can still be recorded.
    """
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ops.pipeline_runs
                   SET status = %s, finished_at = now(), rows_ingested = %s,
                       rows_quarantined = %s, rows_silver = %s, rows_gold = %s, error = %s
                   WHERE run_id = %s""",
                (
                    status,
                    counts.get("rows_ingested", 0),
                    counts.get("rows_quarantined", 0),
                    counts.get("rows_silver", 0),
                    counts.get("rows_gold", 0),
                    error,
                    run_id,
                ),
            )


def mark_stale_runs(conn):
    """Mark runs still flagged 'running' as failed and return how many were fixed.

    A container killed mid-run never gets to write its final status, so its row would stay
    'running' forever. This is only safe because pipeline.py holds an advisory lock first:
    at that point no other run can legitimately be in progress.
    """
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ops.pipeline_runs
                   SET status = 'failed', finished_at = now(),
                       error = 'process died before the run finished'
                   WHERE status = 'running'"""
            )
            return cur.rowcount


def count_quarantined(conn, run_id):
    """How many records this run sent to quarantine (used when a run fails at the gate)."""
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ops.quarantine WHERE run_id = %s", (run_id,))
            return cur.fetchone()[0]
