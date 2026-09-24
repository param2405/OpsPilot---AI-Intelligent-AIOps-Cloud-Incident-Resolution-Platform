# Database Troubleshooting: PostgreSQL Lock Contention and Deadlock Resolution

## Lock Contention Taxonomy & Principles
PostgreSQL utilizes multi-version concurrency control (MVCC) to ensure readers do not block writers and writers do not block readers. However, concurrent write transactions updating overlapping row sets or modifying table schemas acquire row-exclusive or access-exclusive locks that induce queue stalls and deadlocks.

## Diagnostic Queries for Blocked Processes

### Query 1: Active Blocked Statements and Wait Events
Identify which transactions are actively waiting on locks and what events they are waiting on:
```sql
SELECT pid, usename, datname, state, 
       wait_event_type, wait_event, 
       now() - query_start AS duration, 
       query 
FROM pg_stat_activity 
WHERE wait_event_type = 'Lock' 
ORDER BY duration DESC;
```

### Query 2: Lock Contention Dependency Tree
Map the full blocker tree showing which PID is holding locks and which downstream PIDs are queued:
```sql
SELECT 
    activity.pid,
    activity.usename,
    activity.query,
    blocking.pid AS blocking_pid,
    blocking.query AS blocking_query,
    now() - activity.query_start AS waiting_duration
FROM pg_stat_activity activity
JOIN pg_locks c_lock ON activity.pid = c_lock.pid
JOIN pg_locks b_lock ON b_lock.locktype = c_lock.locktype
    AND b_lock.database IS NOT DISTINCT FROM c_lock.database
    AND b_lock.relation IS NOT DISTINCT FROM c_lock.relation
    AND b_lock.page IS NOT DISTINCT FROM c_lock.page
    AND b_lock.tuple IS NOT DISTINCT FROM c_lock.tuple
    AND b_lock.virtualxid IS NOT DISTINCT FROM c_lock.virtualxid
    AND b_lock.transactionid IS NOT DISTINCT FROM c_lock.transactionid
    AND b_lock.classid IS NOT DISTINCT FROM c_lock.classid
    AND b_lock.objid IS NOT DISTINCT FROM c_lock.objid
    AND b_lock.objsubid IS NOT DISTINCT FROM c_lock.objsubid
    AND b_lock.pid != c_lock.pid
JOIN pg_stat_activity blocking ON blocking.pid = b_lock.pid
WHERE NOT c_lock.granted;
```

## Emergency Resolution Tactics

### Tactic 1: Cancel vs Terminate Backend
- Non-destructive cancel:
  ```sql
  SELECT pg_cancel_backend(12345);
  ```
  Sends `SIGINT` to cancel the running statement while keeping the connection open.
- Immediate termination:
  ```sql
  SELECT pg_terminate_backend(12345);
  ```
  Sends `SIGTERM` to abruptly close the database connection and rollback all uncommitted transactions.

### Tactic 2: Preventative Lock Timeouts
Enforce statement and lock timeouts in application session profiles to prevent infinite queueing:
```sql
SET lock_timeout = '3000ms';
SET statement_timeout = '15000ms';
SET idle_in_transaction_session_timeout = '60000ms';
```
When `lock_timeout` expires, PostgreSQL aborts the requesting query with error `55P03: lock_not_available`, shielding the database cluster from cascading connection pool saturation.
