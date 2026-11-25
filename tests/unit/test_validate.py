from pipeline.validate import validate_record


def good():
    """A record that passes every rule; tests tweak one field at a time."""
    return {
        "unique_key": "1",
        "created_date": "2025-01-02T10:00:00.000",
        "closed_date": "2025-01-03T10:00:00.000",
        "agency": "NYPD",
        "complaint_type": "Noise",
        "status": "Closed",
        "latitude": "40.7",
        "longitude": "-73.9",
    }


def rules(record):
    return {v.rule_name for v in validate_record(record)}


def test_valid_record_has_no_violations():
    assert validate_record(good()) == []


def test_missing_agency_is_flagged():
    rec = good()
    del rec["agency"]
    assert "required_field_missing" in rules(rec)


def test_created_in_future_is_flagged():
    rec = good()
    rec["created_date"] = "2099-01-01T10:00:00.000"
    assert "created_in_future" in rules(rec)


def test_closed_before_created_is_flagged():
    rec = good()
    rec["closed_date"] = "2025-01-01T10:00:00.000"
    assert "closed_before_created" in rules(rec)


def test_coordinates_outside_nyc_are_flagged():
    rec = good()
    rec["latitude"] = "10.0"
    assert "coordinates_out_of_range" in rules(rec)


def test_unknown_status_is_flagged():
    rec = good()
    rec["status"] = "Banana"
    assert "invalid_status" in rules(rec)
