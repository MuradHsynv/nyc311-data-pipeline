import uuid

import pytest
from psycopg2.extras import Json, execute_values

from pipeline.db import get_connection
from pipeline.ingest import _load_batch, _start_or_resume
from pipeline.silver import QualityGateError, build_silver


def _make_record(i, bad=False):
    return {
        "unique_key": str(i),
        "created_date": "2025-01-02T10:00:00.000",
        "closed_date": "2025-01-01T10:00:00.000" if bad else "2025-01-03T10:00:00.000",
        "agency": "NYPD",
        "complaint_type": "Noise",
        "status": "Closed",
        "latitude": "40.7",
        "longitude": "-73.9",
    }


def test_quality_gate_rolls_back_silver_and_keeps_quarantine(db_conn, settings):
    run_id = str(uuid.uuid4())
    records = [_make_record(i, bad=(i < 10)) for i in range(100)]
    values = [(r["unique_key"], r["created_date"], Json(r), run_id) for r in records]
    with db_conn:
        with db_conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO bronze.requests_raw
                    (source_id, source_created_at, payload, run_id)
                VALUES %s
                """,
                values,
            )

    quarantine_conn = get_connection(settings)
    try:
        with pytest.raises(QualityGateError):
            build_silver(db_conn, quarantine_conn, run_id, threshold=0.05)
    finally:
        quarantine_conn.close()

    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM silver.service_requests")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM ops.quarantine WHERE run_id = %s", (run_id,))
        assert cur.fetchone()[0] == 10


def test_resume_continues_from_saved_offset_without_duplicates(db_conn):
    run_id = str(uuid.uuid4())
    window_key = "2025-01-01|2025-02-01"

    assert _start_or_resume(db_conn, window_key) == 0

    batch = [_make_record(i) for i in range(5)]
    _load_batch(db_conn, run_id, window_key, batch, next_offset=5000)

    # Simulate crash and restart: checkpoint should resume from 5000.
    assert _start_or_resume(db_conn, window_key) == 5000

    # Replaying the same records must not create duplicates.
    _load_batch(db_conn, run_id, window_key, batch, next_offset=5000)
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*), count(DISTINCT source_id) FROM bronze.requests_raw")
        total, distinct = cur.fetchone()
        assert total == distinct == 5
