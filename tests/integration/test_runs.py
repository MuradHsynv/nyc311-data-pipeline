from datetime import date

from pipeline.runs import count_quarantined, finish_run, mark_stale_runs, start_run


def fetch_run(conn, run_id):
    """Helper: read back the columns the tests care about."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, rows_ingested, rows_gold, error, finished_at "
            "FROM ops.pipeline_runs WHERE run_id = %s",
            (run_id,),
        )
        return cur.fetchone()


def test_start_run_creates_a_running_row(db_conn):
    run_id = start_run(db_conn, "backfill", date(2025, 1, 1), date(2025, 2, 1))
    status, ingested, gold, error, finished_at = fetch_run(db_conn, run_id)
    assert status == "running"
    assert finished_at is None


def test_finish_run_records_counts_and_error(db_conn):
    run_id = start_run(db_conn, "incremental", None, None)
    finish_run(db_conn, run_id, "failed", {"rows_ingested": 120}, "QualityGateError: too many")
    status, ingested, gold, error, finished_at = fetch_run(db_conn, run_id)
    assert status == "failed"
    assert ingested == 120
    assert gold == 0  # missing keys default to 0
    assert "QualityGateError" in error
    assert finished_at is not None


def test_mark_stale_runs_fails_orphaned_runs(db_conn):
    run_id = start_run(db_conn, "backfill", date(2025, 1, 1), date(2025, 2, 1))
    assert mark_stale_runs(db_conn) == 1
    status, _, _, error, _ = fetch_run(db_conn, run_id)
    assert status == "failed"
    assert "died" in error


def test_count_quarantined_counts_only_this_run(db_conn):
    run_id = start_run(db_conn, "incremental", None, None)
    with db_conn:
        with db_conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ops.quarantine (run_id, source_id, rule_name, reason, raw_record)
                   VALUES (%s, 'k1', 'invalid_status', 'bad', '{}'),
                          (%s, 'k2', 'invalid_status', 'bad', '{}')""",
                (run_id, run_id),
            )
    assert count_quarantined(db_conn, run_id) == 2
