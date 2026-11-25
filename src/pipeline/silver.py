"""Builds silver from bronze, quarantines bad rows, and enforces the quality gate."""

import logging
from dataclasses import dataclass
from datetime import datetime

from psycopg2.extras import Json, execute_values

from pipeline.bulk import upsert_via_copy
from pipeline.validate import validate_record

log = logging.getLogger(__name__)

SILVER_TABLE = "silver.service_requests"
SILVER_COLUMNS = [
    "unique_key",
    "created_date",
    "closed_date",
    "agency",
    "agency_name",
    "complaint_type",
    "descriptor",
    "status",
    "borough",
    "city",
    "incident_zip",
    "latitude",
    "longitude",
    "open_data_channel_type",
    "bronze_run_id",
]


class QualityGateError(Exception):
    """Too many records failed validation: stop the run before publishing silver."""


@dataclass
class SilverResult:
    total: int
    valid: int
    invalid: int


def _to_float(value):
    return float(value) if value not in (None, "") else None


def _to_ts(value):
    return datetime.fromisoformat(str(value)).replace(tzinfo=None) if value else None


def to_silver_row(raw, run_id):
    """Convert a VALID raw record into a typed tuple in SILVER_COLUMNS order."""
    return (
        str(raw["unique_key"]).strip(),
        _to_ts(raw["created_date"]),
        _to_ts(raw.get("closed_date")),
        raw["agency"].strip(),
        raw.get("agency_name"),
        raw["complaint_type"].strip(),
        raw.get("descriptor"),
        raw["status"].strip(),
        raw.get("borough"),
        raw.get("city"),
        raw.get("incident_zip"),
        _to_float(raw.get("latitude")),
        _to_float(raw.get("longitude")),
        raw.get("open_data_channel_type"),
        run_id,
    )


def _write_quarantine(conn, bad_rows):
    """Commit quarantine rows immediately. UNIQUE (source_id, rule_name) keeps reruns idempotent."""
    with conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO ops.quarantine (run_id, source_id, rule_name, reason, raw_record)
                VALUES %s
                ON CONFLICT (source_id, rule_name) DO UPDATE SET
                    run_id = EXCLUDED.run_id,
                    reason = EXCLUDED.reason,
                    raw_record = EXCLUDED.raw_record,
                    created_at = now()
                """,
                bad_rows,
            )


def build_silver(silver_conn, quarantine_conn, run_id, threshold, batch_size=10000):
    """Validate every bronze row of this run, then publish valid rows to silver."""
    total = 0
    valid = 0
    invalid = 0

    # A server-side (named) cursor streams bronze in batches instead of loading it all in RAM.
    # Note: silver_conn must be a normal (non-autocommit) connection.
    with silver_conn.cursor(name="bronze_reader") as reader:
        reader.itersize = batch_size
        reader.execute(
            "SELECT source_id, payload FROM bronze.requests_raw WHERE run_id = %s",
            (run_id,),
        )
        while True:
            batch = reader.fetchmany(batch_size)
            if not batch:
                break

            good_rows = []
            bad_rows = []
            for source_id, payload in batch:
                violations = validate_record(payload)
                if not violations:
                    good_rows.append(to_silver_row(payload, run_id))
                    continue

                # Group by rule_name so one INSERT never hits the same (source_id, rule_name) twice.
                by_rule = {}
                for viol in violations:
                    by_rule.setdefault(viol.rule_name, []).append(viol.reason)
                for rule, reasons in by_rule.items():
                    bad_rows.append((run_id, source_id, rule, "; ".join(reasons), Json(payload)))
                invalid += 1

            total += len(batch)
            valid += len(good_rows)

            if bad_rows:
                _write_quarantine(quarantine_conn, bad_rows)
            if good_rows:
                # Not committed yet: silver stays unpublished until the quality gate passes.
                upsert_via_copy(
                    silver_conn,
                    SILVER_TABLE,
                    SILVER_COLUMNS,
                    good_rows,
                    ["unique_key"],
                )

    ratio = invalid / total if total else 0.0
    log.info(
        "validation done: total=%s valid=%s invalid=%s ratio=%.4f",
        total,
        valid,
        invalid,
        ratio,
    )

    # QUALITY GATE: too many failures rolls back silver while quarantine rows remain committed.
    if ratio > threshold:
        silver_conn.rollback()
        raise QualityGateError(f"failure ratio {ratio:.2%} exceeds threshold {threshold:.2%}")

    silver_conn.commit()
    return SilverResult(total=total, valid=valid, invalid=invalid)
