# Performance report

Owner: Sahin Bedelov (#2, database / gold layer)

## Setup

| Item | Value |
|---|---|
| Data | NYC 311 service requests, backfill 2025-01-01 to 2025-06-01 (5 monthly pipeline runs, all `success`) |
| Fact table rows | 1,452,144 (196 MB heap, 14 agencies) |
| PostgreSQL | 16 in docker, default config (`shared_buffers` 128 MB) |
| Queries | [queries/slow_queries.sql](../queries/slow_queries.sql) |
| Fixes | [migrations/004_indexes.sql](../migrations/004_indexes.sql) |

## Method

1. Backfill finished, then `VACUUM ANALYZE gold.fact_service_requests;`. At this point the
   fact table had only its primary key index.
2. BEFORE: each query run with `EXPLAIN (ANALYZE, BUFFERS)` three times. The first run warms
   the cache; the time reported is the third (warm) run.
3. Applied `004_indexes.sql` through the normal migration runner (`apply_migrations`), then
   `VACUUM ANALYZE` again.
4. AFTER: repeated step 2.

Speedup = BEFORE time / AFTER time (warm runs).

## Summary

| Query | Fix | Before (ms) | After (ms) | Speedup |
|---|---|---|---|---|
| Q1 month count | index `(created_date_key)` | 36.6 | 9.5 | 3.8x |
| Q2 recent open | index `(status, created_at)` | 41.2 | 0.106 | 388x |
| Q3 agency top types | index `(agency_sk, complaint_type_sk)` | 30.9 | 1.86 | 16.6x |
| Q4 latest per agency | rewrite to `LATERAL` + index `(agency_sk, created_at DESC)` | > 600,000 (cancelled) | 0.108 | > 5,000,000x |

All three runs per query, in ms:

| Query | BEFORE runs | AFTER runs |
|---|---|---|
| Q1 | 36.6, 35.7, 36.6 | 11.7, 9.9, 9.5 |
| Q2 | 36.9, 40.6, 41.2 | 0.42, 0.10, 0.11 |
| Q3 | 34.3, 31.3, 30.9 | 1.75, 1.80, 1.86 |
| Q4 `DISTINCT ON` | 1156, 1076, 1091 | 525, 460, 485 |
| Q4 `LATERAL` | not run (no index to descend) | 0.107, 0.100, 0.108 |

---

## Q1: requests in one month

| Field | Content |
|---|---|
| Query | `SELECT count(*) FROM gold.fact_service_requests WHERE created_date_key BETWEEN 20250201 AND 20250228;` |
| Problem | `Parallel Seq Scan` over the whole table: 255k matching rows but 1.2M rows removed by filter (398,951 per worker x 3), about 25,000 buffers (the full 196 MB) read every time. |
| Fix | `CREATE INDEX idx_fact_created_date_key ON gold.fact_service_requests (created_date_key);` |
| Before | 36.6 ms, `Parallel Seq Scan`, 25,035 buffers |
| After | 9.5 ms, `Parallel Index Only Scan using idx_fact_created_date_key`, `Heap Fetches: 0`, 222 buffers |
| Speedup | 3.8x |
| Why it works | The index keeps `created_date_key` sorted, so Postgres jumps to February and reads only that range. `count(*)` needs no other column, so it never touches the table (index-only scan). The gain is smaller than for Q2/Q3 because Q1 still has to count 255k rows (18% of the table). |

<details><summary>BEFORE plan</summary>

```
Finalize Aggregate  (actual time=33.731..35.337 rows=1 loops=1)
  Buffers: shared hit=5760 read=19275
  ->  Gather  (actual time=33.625..35.331 rows=3 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        ->  Partial Aggregate  (actual time=31.950..31.951 rows=1 loops=3)
              ->  Parallel Seq Scan on fact_service_requests  (actual time=6.358..28.860 rows=85097 loops=3)
                    Filter: ((created_date_key >= 20250201) AND (created_date_key <= 20250228))
                    Rows Removed by Filter: 398951
                    Buffers: shared hit=5760 read=19275
Execution Time: 36.602 ms
```
</details>

<details><summary>AFTER plan</summary>

```
Finalize Aggregate  (actual time=8.182..9.482 rows=1 loops=1)
  Buffers: shared hit=222
  ->  Gather  (actual time=8.144..9.478 rows=3 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        ->  Partial Aggregate  (actual time=6.670..6.670 rows=1 loops=3)
              ->  Parallel Index Only Scan using idx_fact_created_date_key on fact_service_requests  (actual time=0.015..3.828 rows=85097 loops=3)
                    Index Cond: ((created_date_key >= 20250201) AND (created_date_key <= 20250228))
                    Heap Fetches: 0
                    Buffers: shared hit=222
Execution Time: 9.525 ms
```
</details>

## Q2: open requests created recently

| Field | Content |
|---|---|
| Query | `SELECT unique_key, created_at FROM gold.fact_service_requests WHERE status = 'Open' AND created_at >= '2025-02-01' ORDER BY created_at LIMIT 100;` |
| Problem | Only about 2,260 rows match (`Open` is 0.2% of the table), but the plan reads the whole table (`Rows Removed by Filter: 483295` per worker), then sorts the matches to find the first 100. |
| Fix | `CREATE INDEX idx_fact_status_created ON gold.fact_service_requests (status, created_at);` |
| Before | 41.2 ms, `Parallel Seq Scan` + `Sort` (top-N heapsort) |
| After | 0.106 ms, `Index Scan using idx_fact_status_created`, 88 buffers, no Sort node |
| Speedup | 388x |
| Why it works | Equality column first (`status`), range/sort column second (`created_at`). Inside `status = 'Open'` the entries are already ordered by `created_at`, so Postgres starts at 2025-02-01, reads 100 entries in order and stops: no full scan and no sort. |

<details><summary>BEFORE plan</summary>

```
Limit  (actual time=34.488..36.166 rows=100 loops=1)
  Buffers: shared hit=6160 read=18987
  ->  Gather Merge  (actual time=34.487..36.117 rows=100 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        ->  Sort  (actual time=32.998..33.001 rows=77 loops=3)
              Sort Key: created_at
              Sort Method: top-N heapsort  Memory: 32kB
              ->  Parallel Seq Scan on fact_service_requests  (actual time=7.350..32.833 rows=753 loops=3)
                    Filter: ((created_at >= '2025-02-01 00:00:00'::timestamp without time zone) AND (status = 'Open'::text))
                    Rows Removed by Filter: 483295
                    Buffers: shared hit=6048 read=18987
Execution Time: 41.171 ms
```
</details>

<details><summary>AFTER plan</summary>

```
Limit  (actual time=0.023..0.089 rows=100 loops=1)
  Buffers: shared hit=88
  ->  Index Scan using idx_fact_status_created on fact_service_requests  (actual time=0.022..0.083 rows=100 loops=1)
        Index Cond: ((status = 'Open'::text) AND (created_at >= '2025-02-01 00:00:00'::timestamp without time zone))
        Buffers: shared hit=88
Execution Time: 0.106 ms
```
</details>

## Q3: top complaint types for one agency

| Field | Content |
|---|---|
| Query | `SELECT ct.complaint_type, count(*) AS n FROM gold.fact_service_requests f JOIN gold.dim_complaint_type ct ON ct.complaint_type_sk = f.complaint_type_sk WHERE f.agency_sk = 1 GROUP BY ct.complaint_type ORDER BY n DESC LIMIT 10;` |
| Problem | Agency 1 has 6,889 rows (0.5%), but the fact side is a `Parallel Seq Scan` that removes 481,752 rows per worker before the hash join. |
| Fix | `CREATE INDEX idx_fact_agency_complaint ON gold.fact_service_requests (agency_sk, complaint_type_sk);` |
| Before | 30.9 ms, `Parallel Seq Scan` on the fact table |
| After | 1.86 ms, `Index Only Scan using idx_fact_agency_complaint`, `Heap Fetches: 0`, 27 buffers |
| Speedup | 16.6x |
| Why it works | `agency_sk` first finds the 6,889 rows directly, and `complaint_type_sk` is stored in the same index entry, which is the only other fact column the join needs. So the fact table itself is never read (index-only scan). The remaining time is the hash join and aggregate. |

<details><summary>BEFORE plan</summary>

```
Limit  (actual time=30.632..32.432 rows=1 loops=1)
  ->  Sort  (actual time=30.630..32.429 rows=1 loops=1)
        Sort Key: (count(*)) DESC
        ->  Finalize GroupAggregate  (actual time=30.616..32.415 rows=1 loops=1)
              Group Key: ct.complaint_type
              ->  Gather Merge  (actual time=30.588..32.388 rows=3 loops=1)
                    Workers Planned: 2
                    Workers Launched: 2
                    ->  Partial GroupAggregate  (actual time=28.967..28.968 rows=1 loops=3)
                          ->  Sort  (actual time=28.782..28.850 rows=2296 loops=3)
                                ->  Hash Join  (actual time=0.357..28.440 rows=2296 loops=3)
                                      Hash Cond: (f.complaint_type_sk = ct.complaint_type_sk)
                                      ->  Parallel Seq Scan on fact_service_requests f  (actual time=0.100..27.778 rows=2296 loops=3)
                                            Filter: (agency_sk = 1)
                                            Rows Removed by Filter: 481752
                                            Buffers: shared hit=6336 read=18699
                                      ->  Hash  (actual time=0.234..0.235 rows=1054 loops=3)
                                            ->  Seq Scan on dim_complaint_type ct  (actual time=0.007..0.093 rows=1054 loops=3)
Execution Time: 30.887 ms
```
</details>

<details><summary>AFTER plan</summary>

```
Limit  (actual time=1.814..1.816 rows=1 loops=1)
  Buffers: shared hit=27
  ->  Sort  (actual time=1.813..1.815 rows=1 loops=1)
        Sort Key: (count(*)) DESC
        ->  HashAggregate  (actual time=1.798..1.799 rows=1 loops=1)
              Group Key: ct.complaint_type
              ->  Hash Join  (actual time=0.314..1.163 rows=6889 loops=1)
                    Hash Cond: (f.complaint_type_sk = ct.complaint_type_sk)
                    ->  Index Only Scan using idx_fact_agency_complaint on fact_service_requests f  (actual time=0.023..0.319 rows=6889 loops=1)
                          Index Cond: (agency_sk = 1)
                          Heap Fetches: 0
                          Buffers: shared hit=13
                    ->  Hash  (actual time=0.281..0.282 rows=1054 loops=1)
                          ->  Seq Scan on dim_complaint_type ct  (actual time=0.003..0.076 rows=1054 loops=1)
Execution Time: 1.863 ms
```
</details>

## Q4: latest request per agency

The playbook's BEFORE is a correlated subquery. We measured four versions to separate the
effect of the rewrite from the effect of the index:

| Version | Index `(agency_sk, created_at DESC)` | Time | Main plan node |
|---|---|---|---|
| A. correlated subquery (original) | no | > 600 s, cancelled; estimated about 46 h | `Seq Scan` + `SubPlan` (`Seq Scan` per outer row) |
| B. correlated subquery | yes | 3,710 ms | `Seq Scan` + `SubPlan` (`Index Only Scan`, 1,452,144 loops) |
| C. `DISTINCT ON` rewrite | no | 1,091 ms | `Seq Scan` + `Sort` (external merge, 58 MB on disk) |
| C. `DISTINCT ON` rewrite | yes | 485 ms | `Index Scan` over all 1,452,144 entries + `Unique` |
| D. `LATERAL` rewrite (chosen) | yes | **0.108 ms** | `Nested Loop`: 14 x `Index Scan` with `LIMIT 1` |

| Field | Content |
|---|---|
| Query | BEFORE: `WHERE f.created_at = (SELECT max(f2.created_at) FROM gold.fact_service_requests f2 WHERE f2.agency_sk = f.agency_sk)`. AFTER: `FROM gold.dim_agency a CROSS JOIN LATERAL (SELECT ... WHERE f.agency_sk = a.agency_sk ORDER BY f.created_at DESC LIMIT 1) x` |
| Problem | The subquery runs once per outer row: 1,452,144 times. Without an index each run is a full serial scan of the table (measured 114 ms for the largest agency), so the total is quadratic: about 1.45M x 114 ms = 46 hours. The query was cancelled after 10 minutes. |
| Fix | Rewrite to `LATERAL` over `dim_agency` + `CREATE INDEX idx_fact_agency_created ON gold.fact_service_requests (agency_sk, created_at DESC);` |
| Before | > 600,000 ms (cancelled), plan from plain `EXPLAIN`: estimated cost 63,090,069,298 |
| After | 0.108 ms, 14 index descents |
| Speedup | > 5,000,000x against the 10 minute lower bound |
| Why it works | We only need one row per agency, and there are 14 agencies. With the index sorted by `(agency_sk, created_at DESC)`, the newest request of an agency is the first index entry for that agency, so `LIMIT 1` reads exactly one entry per agency: 14 tiny lookups instead of reading 1.45M rows. `DISTINCT ON` is correct but still walks every index entry, which is why it stays at 485 ms. |

Notes:

- Results of C and D were compared with `EXCEPT`: identical (0 differing rows).
- On ties: if two requests of one agency share the latest `created_at`, A returns both, while
  C and D return one.
- D drives from `gold.dim_agency`, so it relies on every fact `agency_sk` existing there, which
  the foreign key guarantees. Agency versions without facts produce no row (`CROSS JOIN`).

<details><summary>Q4 A: plan of the original query (EXPLAIN only, too slow to ANALYZE)</summary>

```
Seq Scan on fact_service_requests f  (cost=0.00..63090069298.44 rows=7261 width=25)
  Filter: (created_at = (SubPlan 1))
  SubPlan 1
    ->  Aggregate  (cost=43446.11..43446.12 rows=1 width=8)
          ->  Seq Scan on fact_service_requests f2  (cost=0.00..43186.80 rows=103725 width=8)
                Filter: (agency_sk = f.agency_sk)
```

One subplan run, serial, largest agency (`agency_sk = 12`, 666,890 rows):

```
->  Seq Scan on fact_service_requests  (actual time=0.008..93.277 rows=666890 loops=1)
Execution Time: 115.214 ms   (runs: 115.2, 115.2, 114.1)
```
</details>

<details><summary>Q4 B: original query with the index</summary>

```
Seq Scan on fact_service_requests f  (actual time=896.562..3699.298 rows=14 loops=1)
  Filter: (created_at = (SubPlan 2))
  Rows Removed by Filter: 1452130
  SubPlan 2
    ->  Result  (actual time=0.002..0.002 rows=1 loops=1452144)
          InitPlan 1 (returns $1)
            ->  Limit  (actual time=0.002..0.002 rows=1 loops=1452144)
                  ->  Index Only Scan using idx_fact_agency_created on fact_service_requests f2  (actual time=0.002..0.002 rows=1 loops=1452144)
                        Index Cond: ((agency_sk = f.agency_sk) AND (created_at IS NOT NULL))
                        Heap Fetches: 0
Execution Time: 3709.746 ms
```
</details>

<details><summary>Q4 C: DISTINCT ON, without and with the index</summary>

```
-- without index
Unique  (actual time=931.379..1077.955 rows=14 loops=1)
  Buffers: shared hit=7718 read=17323, temp read=14933 written=14961
  ->  Sort  (actual time=931.377..1029.463 rows=1452144 loops=1)
        Sort Key: agency_sk, created_at DESC
        Sort Method: external merge  Disk: 59776kB
        ->  Seq Scan on fact_service_requests  (actual time=2.317..105.870 rows=1452144 loops=1)
Execution Time: 1091.406 ms

-- with index
Result  (actual time=2.143..475.648 rows=14 loops=1)
  ->  Unique  (actual time=0.024..473.506 rows=14 loops=1)
        ->  Index Scan using idx_fact_agency_created on fact_service_requests  (actual time=0.023..403.902 rows=1452144 loops=1)
Execution Time: 485.311 ms
```
</details>

<details><summary>Q4 D: LATERAL with the index (chosen)</summary>

```
Nested Loop  (actual time=0.020..0.092 rows=14 loops=1)
  Buffers: shared hit=57
  ->  Seq Scan on dim_agency a  (actual time=0.005..0.006 rows=14 loops=1)
  ->  Limit  (actual time=0.006..0.006 rows=1 loops=14)
        Buffers: shared hit=56
        ->  Index Scan using idx_fact_agency_created on fact_service_requests f  (actual time=0.006..0.006 rows=1 loops=14)
              Index Cond: (agency_sk = a.agency_sk)
Execution Time: 0.108 ms
```
</details>

---

## Partitioning experiment

Done on a copy (`gold.fact_service_requests_part`, 15 monthly range partitions on
`created_at`, no indexes), so the live loader was untouched. The copy was dropped afterwards.
Both tables were compared without any index on `created_at`, so the difference is pruning
alone.

| Query | Table | Time (warm) | What the plan shows |
|---|---|---|---|
| February on `created_at` | unpartitioned | 35.1 ms | `Parallel Seq Scan` on the whole table |
| February on `created_at` | partitioned | 14.2 ms (2.5x) | only `fact_sr_p_202502` scanned (partition pruning) |
| original Q1 on `created_date_key` | partitioned | 37.1 ms | all 15 partitions scanned, no pruning |

Why we keep the main table unpartitioned:

- A partitioned table's primary key must include the partition column, so the key would become
  `(unique_key, created_at)`. The gold loader's `ON CONFLICT (unique_key)` would no longer have
  a matching unique constraint, so the idempotent upsert would need a redesign.
- Pruning only works when the filter is on the partition column. Our queries filter on
  `created_date_key`, which got no benefit at all (37.1 ms, every partition scanned).
- At 1.45M rows the B-tree index on `created_date_key` is already faster (9.5 ms) than pruning
  (14.2 ms). Partitioning starts to pay off at much larger sizes or for dropping old months.

## Trade-offs of the indexes

| Index | Size |
|---|---|
| `idx_fact_created_date_key` | 9.9 MB |
| `idx_fact_status_created` | 40 MB |
| `idx_fact_agency_complaint` | 10.1 MB |
| `idx_fact_agency_created` | 40 MB |
| total new | about 100 MB (table heap is 196 MB, primary key 57 MB) |

- Every insert or update in the gold load now also writes 4 index entries, so the load gets
  somewhat slower. Applying the migration (all four indexes on 1.45M rows, including container
  start) took under 3 seconds.
- The `(agency_sk, ...)` indexes share the leading column, so a separate `(agency_sk)` index
  is not needed.
- `CREATE INDEX` is used without `CONCURRENTLY` because migrations run in one transaction. It
  locks writes to the fact table while building, which is fine here (3 seconds, and loads are
  serialized by the pipeline's advisory lock anyway).
