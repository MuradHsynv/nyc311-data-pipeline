from datetime import date

import pytest

from pipeline import pipeline as pipeline_module
from pipeline.silver import QualityGateError


def make_record(i, bad=False):
    """Build a synthetic API record; bad=True triggers closed_before_created."""
    return {
        "unique_key": str(i),
        "created_date": "2025-01-02T10:00:00.000",
        "closed_date": "2025-01-01T10:00:00.000" if bad else "2025-01-03T10:00:00.000",
        "agency": "NYPD",
        "agency_name": "Police Department",
        "complaint_type": "Noise",
        "status": "Closed",
        "borough": "BROOKLYN",
        "latitude": "40.7",
        "longitude": "-73.9",
    }


def install_fake_client(monkeypatch, records):
    """Replace SocrataClient so integration tests never hit the network."""

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def iter_pages(self, where=None, start_offset=0):
            rows = records[start_offset:]
            if rows:
                yield rows, start_offset + len(rows)

    monkeypatch.setattr(pipeline_module, "SocrataClient", FakeClient)


def counts(conn):
    """Return [bronze, silver, gold] row counts."""
    out = []
    with conn.cursor() as cur:
        for table in (
            "bronze.requests_raw",
            "silver.service_requests",
            "gold.fact_service_requests",
        ):
            cur.execute("SELECT count(*) FROM " + table)
            out.append(cur.fetchone()[0])
    return out


def test_running_twice_gives_identical_results(db_conn, settings, monkeypatch):
    install_fake_client(monkeypatch, [make_record(i) for i in range(50)])
    window = (date(2025, 1, 1), date(2025, 2, 1))
    pipeline_module.run_pipeline(settings, "backfill", *window)
    first = counts(db_conn)
    pipeline_module.run_pipeline(settings, "backfill", *window)
    assert counts(db_conn) == first == [50, 50, 50]


def test_malformed_batch_trips_quality_gate(db_conn, settings, monkeypatch):
    # 10% bad records against the 5% threshold
    records = [make_record(i, bad=(i < 10)) for i in range(100)]
    install_fake_client(monkeypatch, records)
    with pytest.raises(QualityGateError):
        pipeline_module.run_pipeline(settings, "backfill", date(2025, 1, 1), date(2025, 2, 1))

    with db_conn.cursor() as cur:
        cur.execute("SELECT status, error FROM ops.pipeline_runs")
        status, error = cur.fetchone()
        cur.execute("SELECT count(*) FROM ops.quarantine")
        quarantined = cur.fetchone()[0]

    assert status == "failed" and "QualityGateError" in error
    assert quarantined == 10
    assert counts(db_conn)[1:] == [0, 0]


def test_few_bad_records_are_quarantined_but_run_succeeds(db_conn, settings, monkeypatch):
    # 1% bad records passes the 5% threshold
    records = [make_record(i, bad=(i == 0)) for i in range(100)]
    install_fake_client(monkeypatch, records)
    pipeline_module.run_pipeline(settings, "backfill", date(2025, 1, 1), date(2025, 2, 1))
    assert counts(db_conn) == [100, 99, 99]
