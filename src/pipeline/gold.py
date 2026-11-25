"""Loads the gold star schema from silver. Idempotent: a rerun changes nothing.

Design choices:
- Everything runs as set-based SQL inside one transaction (fastest, and all-or-nothing).
- Only silver rows written by this run are processed (bronze_run_id = run_id).
- SCD2: the first version of an agency gets valid_from = 1970-01-01, later versions get
  the load time. The fact load picks the version that was valid at the request's
  created_date, so history stays correct and reruns give identical results.
- LOCALTIMESTAMP is the transaction start time, so closing the old version and opening
  the new one use the exact same instant (no gaps, no overlaps).
"""

import logging

log = logging.getLogger(__name__)

# Date dimension covering every day touched by this run's silver rows
DIM_DATE_SQL = """
WITH r AS (
    SELECT min(created_date)::date AS lo,
           GREATEST(max(created_date), max(closed_date))::date AS hi
    FROM silver.service_requests WHERE bronze_run_id = %s
)
INSERT INTO gold.dim_date
    (date_key, full_date, year, quarter, month, month_name, day, day_of_week, day_name, is_weekend)
SELECT to_char(g.d, 'YYYYMMDD')::int, g.d::date,
       EXTRACT(YEAR FROM g.d), EXTRACT(QUARTER FROM g.d), EXTRACT(MONTH FROM g.d),
       trim(to_char(g.d, 'Month')), EXTRACT(DAY FROM g.d), EXTRACT(ISODOW FROM g.d),
       trim(to_char(g.d, 'Day')), EXTRACT(ISODOW FROM g.d) IN (6, 7)
FROM r, generate_series(r.lo::timestamp, r.hi::timestamp, interval '1 day') AS g(d)
ON CONFLICT (date_key) DO NOTHING
"""

DIM_COMPLAINT_SQL = """
INSERT INTO gold.dim_complaint_type (complaint_type, descriptor)
SELECT DISTINCT complaint_type, COALESCE(descriptor, 'UNKNOWN')
FROM silver.service_requests WHERE bronze_run_id = %s
ON CONFLICT (complaint_type, descriptor) DO NOTHING
"""

DIM_LOCATION_SQL = """
INSERT INTO gold.dim_location (borough, city, incident_zip)
SELECT DISTINCT COALESCE(borough, 'UNKNOWN'), COALESCE(city, 'UNKNOWN'),
       COALESCE(incident_zip, 'UNKNOWN')
FROM silver.service_requests WHERE bronze_run_id = %s
ON CONFLICT (borough, city, incident_zip) DO NOTHING
"""

# SCD2 staging: one row per agency in this run, with a hash of the tracked attributes
AGENCY_STAGE_SQL = """
CREATE TEMP TABLE _agency_stage ON COMMIT DROP AS
SELECT agency AS agency_code,
       max(agency_name) AS agency_name,
       md5(agency || '|' || COALESCE(max(agency_name), '')) AS row_hash
FROM silver.service_requests WHERE bronze_run_id = %s
GROUP BY agency
"""

# SCD2 step 1: close the current version when the tracked attributes changed
SCD2_CLOSE_SQL = """
UPDATE gold.dim_agency d
SET valid_to = LOCALTIMESTAMP, is_current = FALSE
FROM _agency_stage s
WHERE d.agency_code = s.agency_code AND d.is_current AND d.row_hash <> s.row_hash
"""

# SCD2 step 2: open a new current version for new keys and for keys closed in step 1
SCD2_INSERT_SQL = """
INSERT INTO gold.dim_agency (agency_code, agency_name, row_hash, valid_from, valid_to, is_current)
SELECT s.agency_code, s.agency_name, s.row_hash,
       CASE WHEN EXISTS (SELECT 1 FROM gold.dim_agency x WHERE x.agency_code = s.agency_code)
            THEN LOCALTIMESTAMP ELSE TIMESTAMP '1970-01-01' END,
       NULL, TRUE
FROM _agency_stage s
WHERE NOT EXISTS (
    SELECT 1 FROM gold.dim_agency d WHERE d.agency_code = s.agency_code AND d.is_current
)
"""

FACT_SQL = """
INSERT INTO gold.fact_service_requests
    (unique_key, created_date_key, closed_date_key, created_at, closed_at, agency_sk,
     complaint_type_sk, location_sk, status, resolution_hours, latitude, longitude, load_run_id)
SELECT s.unique_key,
       to_char(s.created_date, 'YYYYMMDD')::int,
       CASE WHEN s.closed_date IS NULL THEN NULL ELSE to_char(s.closed_date, 'YYYYMMDD')::int END,
       s.created_date, s.closed_date, a.agency_sk, ct.complaint_type_sk, l.location_sk, s.status,
       ROUND(EXTRACT(EPOCH FROM (s.closed_date - s.created_date)) / 3600.0, 2),
       s.latitude, s.longitude, s.bronze_run_id
FROM silver.service_requests s
JOIN gold.dim_agency a
  ON a.agency_code = s.agency
 AND s.created_date >= a.valid_from
 AND (a.valid_to IS NULL OR s.created_date < a.valid_to)   -- version valid at creation time
JOIN gold.dim_complaint_type ct
  ON ct.complaint_type = s.complaint_type AND ct.descriptor = COALESCE(s.descriptor, 'UNKNOWN')
JOIN gold.dim_location l
  ON l.borough = COALESCE(s.borough, 'UNKNOWN') AND l.city = COALESCE(s.city, 'UNKNOWN')
 AND l.incident_zip = COALESCE(s.incident_zip, 'UNKNOWN')
WHERE s.bronze_run_id = %s
ON CONFLICT (unique_key) DO UPDATE SET
    created_date_key = EXCLUDED.created_date_key, closed_date_key = EXCLUDED.closed_date_key,
    created_at = EXCLUDED.created_at, closed_at = EXCLUDED.closed_at,
    agency_sk = EXCLUDED.agency_sk, complaint_type_sk = EXCLUDED.complaint_type_sk,
    location_sk = EXCLUDED.location_sk, status = EXCLUDED.status,
    resolution_hours = EXCLUDED.resolution_hours, latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude, load_run_id = EXCLUDED.load_run_id
"""


def load_gold(conn, run_id):
    """Load all gold tables for the silver rows written by run_id. Returns fact rows touched."""
    with conn:  # single transaction: gold is either fully updated or untouched
        with conn.cursor() as cur:
            cur.execute(DIM_DATE_SQL, (run_id,))
            cur.execute(DIM_COMPLAINT_SQL, (run_id,))
            cur.execute(DIM_LOCATION_SQL, (run_id,))
            cur.execute("DROP TABLE IF EXISTS _agency_stage")
            cur.execute(AGENCY_STAGE_SQL, (run_id,))
            cur.execute(SCD2_CLOSE_SQL)
            cur.execute(SCD2_INSERT_SQL)
            cur.execute(FACT_SQL, (run_id,))
            touched = cur.rowcount
    log.info("gold load done for run %s: %s fact rows", run_id, touched)
    return touched
