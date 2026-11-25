"""Proves the gold load keeps SCD2 history correctly and is safe to rerun."""

import uuid

from pipeline.gold import load_gold


def insert_silver(conn, key, agency, agency_name, run_id, created="2025-01-02 10:00"):
    """Helper: put one valid silver row in place (upsert so tests can change a name)."""
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO silver.service_requests
                       (unique_key, created_date, agency, agency_name, complaint_type,
                        status, bronze_run_id)
                   VALUES (%s, %s, %s, %s, 'Noise', 'Closed', %s)
                   ON CONFLICT (unique_key) DO UPDATE SET
                       agency_name = EXCLUDED.agency_name,
                       bronze_run_id = EXCLUDED.bronze_run_id""",
                (key, created, agency, agency_name, run_id),
            )


def fact_agency(conn, key):
    """(agency_name, is_current) of the agency version a fact row is linked to."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT a.agency_name, a.is_current
               FROM gold.fact_service_requests f
               JOIN gold.dim_agency a ON a.agency_sk = f.agency_sk
               WHERE f.unique_key = %s""",
            (key,),
        )
        return cur.fetchone()


def gold_counts(conn):
    """Row counts of every gold table, in a fixed order."""
    tables = ("dim_date", "dim_agency", "dim_location", "dim_complaint_type")
    with conn.cursor() as cur:
        counts = []
        for t in tables + ("fact_service_requests",):
            cur.execute(f"SELECT count(*) FROM gold.{t}")
            counts.append(cur.fetchone()[0])
    return counts


def test_scd2_creates_new_version_when_attribute_changes(db_conn):
    run1, run2 = str(uuid.uuid4()), str(uuid.uuid4())
    insert_silver(db_conn, "k1", "NYPD", "Police Department", run1)
    load_gold(db_conn, run1)
    insert_silver(db_conn, "k1", "NYPD", "NYC Police Department", run2)
    load_gold(db_conn, run2)
    load_gold(db_conn, run2)  # a repeat must not create a third version

    with db_conn.cursor() as cur:
        cur.execute(
            """SELECT agency_name, is_current, valid_to IS NULL
               FROM gold.dim_agency WHERE agency_code = 'NYPD' ORDER BY agency_sk"""
        )
        versions = cur.fetchall()

    assert len(versions) == 2
    assert versions[0] == ("Police Department", False, False)  # old version closed
    assert versions[1] == ("NYC Police Department", True, True)  # new version current


def test_scd2_versions_have_no_gap_or_overlap(db_conn):
    run1, run2 = str(uuid.uuid4()), str(uuid.uuid4())
    insert_silver(db_conn, "k1", "NYPD", "Police Department", run1)
    load_gold(db_conn, run1)
    insert_silver(db_conn, "k1", "NYPD", "NYC Police Department", run2)
    load_gold(db_conn, run2)

    with db_conn.cursor() as cur:
        cur.execute(
            """SELECT valid_from, valid_to FROM gold.dim_agency
               WHERE agency_code = 'NYPD' ORDER BY agency_sk"""
        )
        (_, old_to), (new_from, _) = cur.fetchall()

    assert old_to == new_from  # the old version ends exactly where the new one starts


def test_fact_uses_agency_version_valid_at_created_date(db_conn):
    """As-of join: a request keeps the agency version that was valid when it was created."""
    run1, run2 = str(uuid.uuid4()), str(uuid.uuid4())
    insert_silver(db_conn, "old", "NYPD", "Police Department", run1)
    load_gold(db_conn, run1)

    # The rename arrives in run2, together with a request created after the rename
    insert_silver(db_conn, "old", "NYPD", "NYC Police Department", run2)
    insert_silver(db_conn, "new", "NYPD", "NYC Police Department", run2, created="2100-01-01")
    load_gold(db_conn, run2)

    assert fact_agency(db_conn, "old") == ("Police Department", False)  # history kept
    assert fact_agency(db_conn, "new") == ("NYC Police Department", True)


def test_gold_load_is_idempotent(db_conn):
    run = str(uuid.uuid4())
    insert_silver(db_conn, "k2", "DOT", "Department of Transportation", run)
    load_gold(db_conn, run)
    first = gold_counts(db_conn)

    load_gold(db_conn, run)

    assert gold_counts(db_conn) == first
    assert first[-1] == 1  # exactly one fact row
