CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS ops;

-- One row per pipeline run (run tracking, owned by #3, table created by #2)
CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    run_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mode              TEXT NOT NULL CHECK (mode IN ('incremental', 'backfill')),
    date_from         DATE,
    date_to           DATE,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at       TIMESTAMPTZ,
    status            TEXT NOT NULL DEFAULT 'running'
                      CHECK (status IN ('running', 'success', 'failed')),
    rows_ingested     INTEGER NOT NULL DEFAULT 0,
    rows_quarantined  INTEGER NOT NULL DEFAULT 0,
    rows_silver       INTEGER NOT NULL DEFAULT 0,
    rows_gold         INTEGER NOT NULL DEFAULT 0,
    error             TEXT
);

-- Checkpoints that make ingestion resumable (one row per source + date window)
CREATE TABLE IF NOT EXISTS ops.ingestion_state (
    source       TEXT NOT NULL,
    window_key   TEXT NOT NULL,          -- e.g. '2025-01-01|2025-02-01'
    next_offset  BIGINT NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'in_progress'
                 CHECK (status IN ('in_progress', 'complete')),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source, window_key)
);

-- Bad records are never dropped silently: they land here with the reason
CREATE TABLE IF NOT EXISTS ops.quarantine (
    id          BIGSERIAL PRIMARY KEY,
    run_id      UUID NOT NULL,
    source_id   TEXT NOT NULL,
    rule_name   TEXT NOT NULL,
    reason      TEXT NOT NULL,
    raw_record  JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, rule_name)        -- makes quarantine writes idempotent
);
