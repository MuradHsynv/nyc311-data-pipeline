-- BRONZE: raw payload exactly as received. source_id is the API unique_key.
CREATE TABLE IF NOT EXISTS bronze.requests_raw (
    source_id          TEXT PRIMARY KEY,
    source_created_at  TIMESTAMP,            -- copied out of payload for filtering and watermarks
    payload            JSONB NOT NULL,
    run_id             UUID NOT NULL,        -- the run that last wrote this row
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bronze_run ON bronze.requests_raw (run_id);
CREATE INDEX IF NOT EXISTS idx_bronze_created ON bronze.requests_raw (source_created_at);

-- SILVER: typed, validated, one row per unique_key
CREATE TABLE IF NOT EXISTS silver.service_requests (
    unique_key              TEXT PRIMARY KEY,
    created_date            TIMESTAMP NOT NULL,
    closed_date             TIMESTAMP,
    agency                  TEXT NOT NULL,
    agency_name             TEXT,
    complaint_type          TEXT NOT NULL,
    descriptor              TEXT,
    status                  TEXT NOT NULL,
    borough                 TEXT,
    city                    TEXT,
    incident_zip            TEXT,
    latitude                DOUBLE PRECISION,
    longitude               DOUBLE PRECISION,
    open_data_channel_type  TEXT,
    bronze_run_id           UUID NOT NULL,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_silver_created ON silver.service_requests (created_date);
