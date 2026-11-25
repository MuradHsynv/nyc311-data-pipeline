-- Candidate slow queries on the gold fact table (about 1M rows).
-- Measured BEFORE and AFTER migrations/004_indexes.sql; results in docs/performance_report.md.
-- Run: docker compose exec -T postgres psql -U pipeline -d nyc311 -f - < queries/slow_queries.sql
-- To see plans, prefix each statement with EXPLAIN (ANALYZE, BUFFERS).

-- Q1: requests in one month (date range filter on the fact table)
SELECT count(*) FROM gold.fact_service_requests
WHERE created_date_key BETWEEN 20250201 AND 20250228;

-- Q2: open requests created recently (selective filter on two columns)
SELECT unique_key, created_at FROM gold.fact_service_requests
WHERE status = 'Open' AND created_at >= '2025-02-01'
ORDER BY created_at
LIMIT 100;

-- Q3: top complaint types for one agency (join plus aggregate)
SELECT ct.complaint_type, count(*) AS n
FROM gold.fact_service_requests f
JOIN gold.dim_complaint_type ct ON ct.complaint_type_sk = f.complaint_type_sk
WHERE f.agency_sk = 1
GROUP BY ct.complaint_type
ORDER BY n DESC
LIMIT 10;

-- Q4 BEFORE: latest request per agency using a correlated subquery (slow)
SELECT f.agency_sk, f.unique_key, f.created_at
FROM gold.fact_service_requests f
WHERE f.created_at = (
    SELECT max(f2.created_at) FROM gold.fact_service_requests f2
    WHERE f2.agency_sk = f.agency_sk
);

-- Q4 AFTER (rewrite): DISTINCT ON does one ordered pass per agency
SELECT DISTINCT ON (agency_sk) agency_sk, unique_key, created_at
FROM gold.fact_service_requests
ORDER BY agency_sk, created_at DESC;
