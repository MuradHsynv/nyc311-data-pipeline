-- Indexes for the slow gold queries (queries/slow_queries.sql).
-- Added only after the BEFORE measurements; see docs/performance_report.md.
-- Plain CREATE INDEX (not CONCURRENTLY): migrations run inside one transaction.

-- Q1: range filter on created_date_key -> index range scan instead of a full Seq Scan.
CREATE INDEX IF NOT EXISTS idx_fact_created_date_key
    ON gold.fact_service_requests (created_date_key);

-- Q2: equality on status, then range + ORDER BY on created_at.
-- Rows come out of the index already sorted, so LIMIT 100 stops after 100 rows.
CREATE INDEX IF NOT EXISTS idx_fact_status_created
    ON gold.fact_service_requests (status, created_at);

-- Q3: filter on agency_sk; complaint_type_sk is in the index so the
-- aggregate can be fed by an index-only scan (no heap visits after VACUUM).
CREATE INDEX IF NOT EXISTS idx_fact_agency_complaint
    ON gold.fact_service_requests (agency_sk, complaint_type_sk);

-- Q4: max(created_at) per agency_sk -> one index descent per agency.
CREATE INDEX IF NOT EXISTS idx_fact_agency_created
    ON gold.fact_service_requests (agency_sk, created_at DESC);
