-- DATE DIMENSION: one row per calendar day, key like 20250102
CREATE TABLE IF NOT EXISTS gold.dim_date (
    date_key     INTEGER PRIMARY KEY,
    full_date    DATE NOT NULL UNIQUE,
    year         SMALLINT NOT NULL,
    quarter      SMALLINT NOT NULL,
    month        SMALLINT NOT NULL,
    month_name   TEXT NOT NULL,
    day          SMALLINT NOT NULL,
    day_of_week  SMALLINT NOT NULL,      -- ISO: 1 = Monday ... 7 = Sunday
    day_name     TEXT NOT NULL,
    is_weekend   BOOLEAN NOT NULL
);

-- AGENCY DIMENSION, SCD TYPE 2: history is kept as extra rows (versions)
CREATE TABLE IF NOT EXISTS gold.dim_agency (
    agency_sk    BIGSERIAL PRIMARY KEY,      -- surrogate key: one per VERSION
    agency_code  TEXT NOT NULL,              -- business key
    agency_name  TEXT,
    row_hash     TEXT NOT NULL,              -- md5 of tracked attributes: cheap change detection
    valid_from   TIMESTAMP NOT NULL,
    valid_to     TIMESTAMP,                  -- NULL while the version is current
    is_current   BOOLEAN NOT NULL DEFAULT TRUE
);
-- At most ONE current version per business key
CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_agency_current
    ON gold.dim_agency (agency_code) WHERE is_current;

CREATE TABLE IF NOT EXISTS gold.dim_location (
    location_sk   BIGSERIAL PRIMARY KEY,
    borough       TEXT NOT NULL,
    city          TEXT NOT NULL,
    incident_zip  TEXT NOT NULL,
    UNIQUE (borough, city, incident_zip)     -- NULLs become 'UNKNOWN' before loading
);

CREATE TABLE IF NOT EXISTS gold.dim_complaint_type (
    complaint_type_sk  BIGSERIAL PRIMARY KEY,
    complaint_type     TEXT NOT NULL,
    descriptor         TEXT NOT NULL,
    UNIQUE (complaint_type, descriptor)
);

-- FACT TABLE: one row per service request (grain = one 311 request)
CREATE TABLE IF NOT EXISTS gold.fact_service_requests (
    unique_key         TEXT PRIMARY KEY,
    created_date_key   INTEGER NOT NULL REFERENCES gold.dim_date (date_key),
    closed_date_key    INTEGER REFERENCES gold.dim_date (date_key),
    created_at         TIMESTAMP NOT NULL,
    closed_at          TIMESTAMP,
    agency_sk          BIGINT NOT NULL REFERENCES gold.dim_agency (agency_sk),
    complaint_type_sk  BIGINT NOT NULL REFERENCES gold.dim_complaint_type (complaint_type_sk),
    location_sk        BIGINT NOT NULL REFERENCES gold.dim_location (location_sk),
    status             TEXT NOT NULL,        -- degenerate dimension
    resolution_hours   NUMERIC(12, 2),
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    load_run_id        UUID NOT NULL
);
