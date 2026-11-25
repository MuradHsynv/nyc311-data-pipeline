"""Row-level validation rules. Returns violations instead of raising, so callers can quarantine."""

from dataclasses import dataclass
from datetime import datetime

REQUIRED_FIELDS = ("unique_key", "created_date", "agency", "complaint_type", "status")

# Verified against live NYC 311 API ($group=status in docs/api_samples.md).
ALLOWED_STATUS = {
    "Assigned",
    "Cancel",
    "Closed",
    "Draft",
    "Email Sent",
    "In Progress",
    "Open",
    "Pending",
    "Started",
    "Unspecified",
}

# Rough bounding box of New York City.
LAT_RANGE = (40.3, 41.1)
LON_RANGE = (-74.5, -73.5)


@dataclass(frozen=True)
class Violation:
    """One failed rule: a short machine name plus a human-readable reason."""

    rule_name: str
    reason: str


def _parse_ts(value):
    """Parse a Socrata floating timestamp such as 2025-01-02T10:00:00.000."""
    return datetime.fromisoformat(str(value)).replace(tzinfo=None)


def validate_record(raw):
    """Return a list of Violations for one raw record (empty list = valid)."""
    violations = []

    # Rule: required fields
    for field in REQUIRED_FIELDS:
        if not str(raw.get(field) or "").strip():
            violations.append(Violation("required_field_missing", f"{field} is missing or empty"))

    # Rules: created_date
    created = None
    if raw.get("created_date"):
        try:
            created = _parse_ts(raw["created_date"])
            if created > datetime.now():
                violations.append(Violation("created_in_future", "created_date is in the future"))
        except (ValueError, TypeError):
            violations.append(Violation("invalid_created_date", "cannot parse created_date"))

    # Rules: closed_date and ordering
    closed = None
    if raw.get("closed_date"):
        try:
            closed = _parse_ts(raw["closed_date"])
        except (ValueError, TypeError):
            violations.append(Violation("invalid_closed_date", "cannot parse closed_date"))

    if created and closed and closed < created:
        violations.append(
            Violation(
                "closed_before_created",
                "closed_date is earlier than created_date",
            )
        )

    # Rule: status enum
    status = raw.get("status")
    if status and status not in ALLOWED_STATUS:
        violations.append(Violation("invalid_status", f"unexpected status: {status}"))

    # Rule: coordinates (only checked when present)
    for field, (low, high) in (("latitude", LAT_RANGE), ("longitude", LON_RANGE)):
        if raw.get(field) not in (None, ""):
            try:
                value = float(raw[field])
            except (ValueError, TypeError):
                violations.append(Violation("coordinates_out_of_range", f"{field} is not a number"))
                continue
            if not low <= value <= high:
                violations.append(
                    Violation("coordinates_out_of_range", f"{field} outside NYC bounds")
                )

    return violations
