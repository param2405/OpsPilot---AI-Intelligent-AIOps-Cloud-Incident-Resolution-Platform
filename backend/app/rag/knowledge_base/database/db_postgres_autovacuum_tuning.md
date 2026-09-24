# Database Troubleshooting: Autovacuum Stalling and Table Bloat Remediation

## Overview & Consequences of Table Bloat
In PostgreSQL MVCC, an `UPDATE` writes a new tuple version and marks the existing tuple dead, while a `DELETE` marks tuples dead without reclaiming storage. If the autovacuum daemon cannot keep pace with table churn, tables and indexes experience severe physical bloat, leading to cache thrashing and sequential scan degradation.

## Bloat Detection Queries
Check dead tuple ratios across production tables:
```sql
SELECT relname, n_live_tup, n_dead_tup, 
       round(n_dead_tup * 100.0 / nullif(n_live_tup + n_dead_tup, 0), 2) AS dead_tuple_pct,
       last_vacuum, last_autovacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY dead_tuple_pct DESC;
```
If `dead_tuple_pct` exceeds 20% on tables with over 100,000 tuples, manual intervention or aggressive tuning is warranted.

## Autovacuum Worker Starvation Symptoms
Check currently running vacuum operations:
```sql
SELECT pid, phase, heap_blks_total, heap_blks_scanned, 
       heap_blks_vacuumed, index_vacuum_count 
FROM pg_stat_progress_vacuum;
```
If workers remain stuck on single large tables for multiple days, workers are being cost-throttled by default resource limits.

## Tuning Strategy & Parameter Adjustments

### Global Configuration (`postgresql.conf`)
Increase worker concurrency and throughput limits:
```properties
autovacuum_max_workers = 6
autovacuum_vacuum_cost_limit = 2000
autovacuum_vacuum_cost_delay = 2ms
maintenance_work_mem = '2GB'
```

### Table-Specific Overrides for High-Write Tables
For append-heavy and update-heavy tables such as `telemetry_events` and `audit_logs`:
```sql
ALTER TABLE telemetry_events SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_vacuum_cost_limit = 10000,
    autovacuum_vacuum_cost_delay = 0
);
```

## Emergency Online Re-Indexing and Vacuuming
Reclaim dead disk pages without taking an Exclusive Table Lock:
```sql
VACUUM (PARALLEL 4, ANALYZE, VERBOSE) telemetry_events;
REINDEX TABLE CONCURRENTLY telemetry_events;
```
