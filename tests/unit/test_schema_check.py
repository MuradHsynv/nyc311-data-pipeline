import pytest

from pipeline.schema_check import SchemaDriftError, check_schema


def sample_row():
    return {
        "unique_key": "1",
        "created_date": "2025-01-02T10:00:00.000",
        "agency": "NYPD",
        "complaint_type": "Noise",
        "status": "Closed",
    }


def test_normal_page_returns_no_warnings():
    assert check_schema([sample_row()]) == []


def test_new_column_returns_warning():
    row = dict(sample_row(), brand_new_column="value")
    warnings = check_schema([row])
    assert len(warnings) == 1
    assert "brand_new_column" in warnings[0]


def test_missing_core_column_raises_error():
    row = sample_row()
    del row["status"]
    with pytest.raises(SchemaDriftError):
        check_schema([row])
