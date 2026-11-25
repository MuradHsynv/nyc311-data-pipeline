"""Detects when the Socrata API response shape changes (schema drift)."""

# Columns that MUST appear somewhere in every page, or the API broke our contract.
CORE_COLUMNS = {
    "unique_key",
    "created_date",
    "agency",
    "complaint_type",
    "status",
}

# Union of columns observed in live NYC 311 responses (see docs/api_samples.md).
# Any column outside this set triggers a non-fatal warning.
KNOWN_COLUMNS = CORE_COLUMNS | {
    ":@computed_region_92fq_4b7q",
    ":@computed_region_f5dn_yrer",
    ":@computed_region_sbqj_enih",
    ":@computed_region_yeji_bk3q",
    "address_type",
    "agency_name",
    "bbl",
    "borough",
    "city",
    "closed_date",
    "community_board",
    "council_district",
    "cross_street_1",
    "cross_street_2",
    "descriptor",
    "descriptor_2",
    "due_date",
    "facility_type",
    "incident_address",
    "incident_zip",
    "intersection_street_1",
    "intersection_street_2",
    "landmark",
    "latitude",
    "location",
    "location_type",
    "longitude",
    "open_data_channel_type",
    "park_borough",
    "park_facility_name",
    "police_precinct",
    "resolution_action_updated_date",
    "resolution_description",
    "street_name",
    "taxi_pick_up_location",
    "vehicle_type",
    "x_coordinate_state_plane",
    "y_coordinate_state_plane",
}


class SchemaDriftError(Exception):
    """A core column disappeared from the API response: stop the run."""


def check_schema(rows):
    """Return a list of warnings; raise SchemaDriftError if a core column is gone."""
    if not rows:
        return []

    seen = set()
    for record in rows:
        # Union across the whole page because Socrata omits null fields per row.
        seen.update(record.keys())

    missing_core = CORE_COLUMNS - seen
    if missing_core:
        raise SchemaDriftError("core columns missing from API: " + ", ".join(sorted(missing_core)))

    warnings = []
    new_columns = seen - KNOWN_COLUMNS
    if new_columns:
        warnings.append("new columns appeared in API: " + ", ".join(sorted(new_columns)))

    return warnings
