"""Pure validation and type-coercion rules for Bronze -> Silver NYC 311 records."""

from datetime import datetime

# Live statuses observed in docs/api_samples.md ($group=status).
ALLOWED_STATUS = {
    "Assigned",
    "Cancel",
    "Closed",
    "In Progress",
    "Open",
    "Pending",
    "Started",
    "Unspecified",
}

REQUIRED_FIELDS = (
    "unique_key",
    "created_date",
    "agency",
    "complaint_type",
    "status",
)

# Bounding box covering all five NYC boroughs.
NYC_LAT_MIN, NYC_LAT_MAX = 40.4, 41.0
NYC_LON_MIN, NYC_LON_MAX = -74.3, -73.6


def _clean_str(value):
    """Return stripped string, or None if missing/blank."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _parse_timestamp(value):
    """Parse an ISO-8601 timestamp into a naive datetime, or return None on failure."""
    text = _clean_str(value)
    if text is None:
        return None
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    # Silver timestamp columns are timezone-naive; normalize to avoid naive/aware comparisons.
    return dt.replace(tzinfo=None)


def _parse_float(value):
    """Parse a coordinate value into float, or return None on failure."""
    text = _clean_str(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def validate_record(raw):
    """Validate and coerce one raw Socrata JSON dict for silver.service_requests.

    Returns:
        (cleaned_dict, []) when valid.
        (None, [(rule_name, reason), ...]) when one or more rules fail.
    """
    errors = []

    # 1. Required fields must be present and non-empty.
    missing = [field for field in REQUIRED_FIELDS if _clean_str(raw.get(field)) is None]
    if missing:
        errors.append(("missing_required", "missing required fields: " + ", ".join(missing)))

    # 2. Timestamps: created_date is required; closed_date is optional.
    created_dt = None
    raw_created = _clean_str(raw.get("created_date"))
    if raw_created is not None:
        created_dt = _parse_timestamp(raw_created)
        if created_dt is None:
            errors.append(("invalid_created_date", f"unparseable created_date: {raw_created!r}"))

    closed_dt = None
    raw_closed = _clean_str(raw.get("closed_date"))
    if raw_closed is not None:
        closed_dt = _parse_timestamp(raw_closed)
        if closed_dt is None:
            errors.append(("invalid_closed_date", f"unparseable closed_date: {raw_closed!r}"))

    # 3. Date consistency: closed_date cannot be earlier than created_date.
    if created_dt is not None and closed_dt is not None and closed_dt < created_dt:
        errors.append(
            (
                "closed_before_created",
                f"closed_date ({closed_dt.isoformat()}) < created_date ({created_dt.isoformat()})",
            )
        )

    # 4. Status must match known NYC 311 values.
    status = _clean_str(raw.get("status"))
    if status is not None and status not in ALLOWED_STATUS:
        errors.append(("invalid_status", f"unexpected status: {status!r}"))

    # 5. Coordinates: both null is valid; otherwise both must be floats inside NYC bounds.
    raw_lat = _clean_str(raw.get("latitude"))
    raw_lon = _clean_str(raw.get("longitude"))
    lat = None
    lon = None
    if raw_lat is not None or raw_lon is not None:
        lat = _parse_float(raw_lat)
        lon = _parse_float(raw_lon)
        if lat is None or lon is None:
            errors.append(
                (
                    "invalid_coordinates",
                    f"incomplete or non-numeric coordinates: lat={raw_lat!r}, lon={raw_lon!r}",
                )
            )
        elif not (NYC_LAT_MIN <= lat <= NYC_LAT_MAX and NYC_LON_MIN <= lon <= NYC_LON_MAX):
            errors.append(
                (
                    "invalid_coordinates",
                    f"coordinates outside NYC bounds: lat={lat}, lon={lon}",
                )
            )

    if errors:
        return None, errors

    cleaned = {
        "unique_key": _clean_str(raw.get("unique_key")),
        "created_date": created_dt,
        "closed_date": closed_dt,
        "agency": _clean_str(raw.get("agency")),
        "agency_name": _clean_str(raw.get("agency_name")),
        "complaint_type": _clean_str(raw.get("complaint_type")),
        "descriptor": _clean_str(raw.get("descriptor")),
        "status": status,
        "borough": _clean_str(raw.get("borough")),
        "city": _clean_str(raw.get("city")),
        "incident_zip": _clean_str(raw.get("incident_zip")),
        "latitude": lat,
        "longitude": lon,
        "open_data_channel_type": _clean_str(raw.get("open_data_channel_type")),
    }
    return cleaned, []
