-- Analytics on the gold star schema (CTEs and window functions).
-- Run against a loaded database:
--   docker compose exec -T postgres psql -U pipeline -d nyc311 -f - < queries/analytics.sql
--
-- Agency questions group by agency_code (the business key), so every SCD2 version of an
-- agency counts towards the same agency.


-- A1: monthly volume with month-over-month change (LAG)
WITH monthly AS (
    SELECT d.year, d.month, COUNT(*) AS requests
    FROM gold.fact_service_requests f
    JOIN gold.dim_date d ON d.date_key = f.created_date_key
    GROUP BY d.year, d.month
)
SELECT year, month, requests,
       LAG(requests) OVER w AS prev_month,
       ROUND(100.0 * (requests - LAG(requests) OVER w)
             / NULLIF(LAG(requests) OVER w, 0), 1) AS mom_change_pct
FROM monthly
WINDOW w AS (ORDER BY year, month)
ORDER BY year, month;


-- A2: top 5 complaint types per borough (RANK over a partition; ties share a rank)
WITH counts AS (
    SELECT l.borough, ct.complaint_type, COUNT(*) AS requests
    FROM gold.fact_service_requests f
    JOIN gold.dim_location l ON l.location_sk = f.location_sk
    JOIN gold.dim_complaint_type ct ON ct.complaint_type_sk = f.complaint_type_sk
    GROUP BY l.borough, ct.complaint_type
), ranked AS (
    SELECT *, RANK() OVER (PARTITION BY borough ORDER BY requests DESC) AS rnk
    FROM counts
)
SELECT borough, complaint_type, requests, rnk
FROM ranked
WHERE rnk <= 5
ORDER BY borough, rnk, complaint_type;


-- A3: agency resolution time, median and p90, ranked by slowest (percentiles plus RANK)
-- Only closed requests with a sane duration; agencies need 100+ of them to be ranked.
WITH stats AS (
    SELECT a.agency_code, COUNT(*) AS closed_requests,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY f.resolution_hours) AS median_hours,
           percentile_cont(0.9) WITHIN GROUP (ORDER BY f.resolution_hours) AS p90_hours
    FROM gold.fact_service_requests f
    JOIN gold.dim_agency a ON a.agency_sk = f.agency_sk
    WHERE f.resolution_hours >= 0
    GROUP BY a.agency_code
    HAVING COUNT(*) >= 100
)
SELECT agency_code, closed_requests,
       ROUND(median_hours::numeric, 1) AS median_hours,
       ROUND(p90_hours::numeric, 1) AS p90_hours,
       RANK() OVER (ORDER BY p90_hours DESC) AS slowest_rank
FROM stats
ORDER BY slowest_rank, agency_code;


-- A4: daily volume, running total and 7-day moving average (frame clause)
WITH daily AS (
    SELECT d.full_date, COUNT(*) AS requests
    FROM gold.fact_service_requests f
    JOIN gold.dim_date d ON d.date_key = f.created_date_key
    GROUP BY d.full_date
)
SELECT full_date, requests,
       SUM(requests) OVER (ORDER BY full_date) AS running_total,
       ROUND(AVG(requests) OVER (ORDER BY full_date
                                 ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1) AS moving_avg_7d
FROM daily
ORDER BY full_date;


-- A5: each borough's share of every complaint type (SUM as a window)
WITH by_type AS (
    SELECT ct.complaint_type, l.borough, COUNT(*) AS requests
    FROM gold.fact_service_requests f
    JOIN gold.dim_location l ON l.location_sk = f.location_sk
    JOIN gold.dim_complaint_type ct ON ct.complaint_type_sk = f.complaint_type_sk
    GROUP BY ct.complaint_type, l.borough
)
SELECT complaint_type, borough, requests,
       ROUND(100.0 * requests / SUM(requests) OVER (PARTITION BY complaint_type), 1)
           AS pct_of_type
FROM by_type
ORDER BY complaint_type, requests DESC, borough;


-- A6: busiest weekday per agency (ROW_NUMBER, keep rank 1; ties go to the earlier weekday)
WITH by_dow AS (
    SELECT a.agency_code, d.day_of_week, d.day_name, COUNT(*) AS requests
    FROM gold.fact_service_requests f
    JOIN gold.dim_agency a ON a.agency_sk = f.agency_sk
    JOIN gold.dim_date d ON d.date_key = f.created_date_key
    GROUP BY a.agency_code, d.day_of_week, d.day_name
), ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY agency_code
                              ORDER BY requests DESC, day_of_week) AS rn
    FROM by_dow
)
SELECT agency_code, day_name, requests
FROM ranked
WHERE rn = 1
ORDER BY requests DESC, agency_code;
