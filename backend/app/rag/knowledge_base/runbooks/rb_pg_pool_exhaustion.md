# Runbook: PostgreSQL Connection Pool Exhaustion (ERR_POOL_EXHAUSTED)

## Overview & Scope
This operational runbook provides diagnostic and remediation procedures for PostgreSQL connection pool exhaustion events impacting the `order-service` and core backend APIs.

## Symptoms & Alert Criteria
Alert `PostgresConnectionPoolSaturated` fires when:
- Application logs show `HikariPool-1 - Connection is not available, request timed out after 30000ms`.
- Client requests fail with HTTP 503 `Service Unavailable` or HTTP 504 `Gateway Timeout`.
- Active database connections reach >= 92% of configured `max_connections` (threshold: 184/200).
- Queue wait time on pool acquisition exceeds 5000ms.

## Diagnostic Steps

### Step 1: Inspect Active Database Connections
Execute the following diagnostic query in `psql` to view connection counts grouped by state:
```sql
SELECT state, count(*) 
FROM pg_stat_activity 
GROUP BY state;
```

### Step 2: Identify Long-Running or Leaked Transactions
Detect sessions trapped in `idle in transaction` state for longer than 60 seconds:
```sql
SELECT pid, usename, client_addr, state, 
       now() - state_change AS state_duration, 
       query 
FROM pg_stat_activity 
WHERE state = 'idle in transaction' 
  AND now() - state_change > interval '60 seconds'
ORDER BY state_duration DESC;
```

### Step 3: Check for Lock Blockers
Query for transaction lock chains blocking incoming connections:
```sql
SELECT blocked_locks.pid     AS blocked_pid,
       blocking_locks.pid    AS blocking_pid,
       blocked_activity.query    AS blocked_statement,
       blocking_activity.query   AS current_statement_in_blocking_process
FROM  pg_catalog.pg_locks         blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks         blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

## Remediation & Recovery

### Action 1: Terminate Leaked Idle Sessions
Terminate the rogue connections holding transactions open:
```sql
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle in transaction' 
  AND now() - state_change > interval '120 seconds';
```

### Action 2: Scale PgBouncer Connection Pool
If connection pressure is due to sudden traffic spikes:
1. Edit `/etc/pgbouncer/pgbouncer.ini` or Kubernetes ConfigMap:
   - Increase `default_pool_size` from 25 to 50.
   - Set `reserve_pool_size = 15`.
2. Reload PgBouncer configuration without dropping connections:
   ```bash
   kill -HUP $(pgrep pgbouncer)
   ```

### Action 3: Application Pool Adjustments
If the service continues to exhaust connections, adjust application runtime properties in `order-service`:
- `spring.datasource.hikari.maximum-pool-size=30`
- `spring.datasource.hikari.connection-timeout=15000`
- `spring.datasource.hikari.idle-timeout=300000`
- `spring.datasource.hikari.max-lifetime=900000`
Restart the deployment gracefully:
```bash
kubectl rollout restart deployment/order-service -n production
```
