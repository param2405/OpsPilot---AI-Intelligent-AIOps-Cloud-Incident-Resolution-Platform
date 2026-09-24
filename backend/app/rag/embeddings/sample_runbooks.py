"""Canonical engineering runbooks for semantic similarity search in OpsPilot AI."""

from typing import Any, Dict, List

CANONICAL_RUNBOOKS: List[Dict[str, Any]] = [
    {
        "id": "RB-001",
        "title": "PostgreSQL Connection Pool Saturation & Lock Contention",
        "failure_domain": "database",
        "symptoms": "HikariCP connection pool timeout waiting for connection. Active DB connections reached 100/100 cap. Queries queued and timed out after 5000ms. Error rate spiked on database transactions.",
        "steps": [
            "1. Inspect active PostgreSQL backends via `SELECT * FROM pg_stat_activity WHERE state != 'idle';`",
            "2. Identify long-running transactions blocking tables and terminate orphaned locks using `SELECT pg_terminate_backend(pid);`",
            "3. Temporarily expand max HikariCP pool size from 100 to 150 on payment-service and restart idle replicas.",
            "4. Verify connection count returns below 70% threshold.",
        ],
        "tags": ["postgres", "hikaricp", "connection_pool", "timeout", "deadlock"],
    },
    {
        "id": "RB-002",
        "title": "JVM Heap Exhaustion and Container OOM-Kill Recovery",
        "failure_domain": "application",
        "symptoms": "Memory usage steadily climbed to 98% over 3 hours. Severe garbage collection pauses (Stop-The-World GC > 4000ms). Container terminated with exit code 137 (SIGKILL). OutOfMemoryError.",
        "steps": [
            "1. Confirm container exit code 137 in Kubernetes pod termination metadata.",
            "2. Inspect recent heap dumps in S3 bucket /heapdumps/{service_name}/ using Eclipse Memory Analyzer (MAT).",
            "3. Identify leaky collections or unbounded in-memory caches.",
            "4. Adjust pod memory limit to 2Gi and enable G1GC low-latency garbage collector: `-XX:+UseG1GC -XX:MaxGCPauseMillis=200`.",
            "5. Roll out patched build with TTL-bounded caching.",
        ],
        "tags": ["java", "jvm", "oom", "heap", "garbage_collection", "sigkill"],
    },
    {
        "id": "RB-003",
        "title": "Catastrophic Regex Backtracking and Worker CPU Starvation",
        "failure_domain": "application",
        "symptoms": "CPU usage pegged at 100% across all worker threads. Service failed liveness probes. p95 latency skyrocketed from 25ms to 2800ms. Worker thread hung in JWT regex claims verification.",
        "steps": [
            "1. Capture thread dump from running containers using `jstack` or profiling endpoint.",
            "2. Locate threads blocked in `java.util.regex.Pattern` or equivalent parsing loop.",
            "3. Identify malformed or oversized authorization headers incoming through API gateway.",
            "4. Enforce header size limits at NGINX/Envoy ingress (max 4KB).",
            "5. Replace vulnerable backtracking regex with deterministic finite automaton (DFA) parser.",
        ],
        "tags": ["cpu", "regex", "backtracking", "starvation", "jwt", "liveness_probe"],
    },
    {
        "id": "RB-004",
        "title": "API Gateway Cascading Latency & Circuit Breaker Mitigation",
        "failure_domain": "network",
        "symptoms": "p95 latency spike from 40ms to 3300ms. Cascading connection buildup on API Gateway. Upstream dependency inventory-service timeout causing 504 Gateway Timeout.",
        "steps": [
            "1. Inspect gateway upstream target metrics to isolate failing downstream dependency.",
            "2. Enable circuit breaker tripping at 50% error rate threshold on inventory-service route.",
            "3. Route degraded traffic to static cached fallback catalog responses.",
            "4. Shed non-essential load using HTTP 429 rate limiting.",
            "5. Verify API gateway p95 latency normalizes below 50ms.",
        ],
        "tags": ["api_gateway", "latency", "circuit_breaker", "cascading", "timeout"],
    },
    {
        "id": "RB-005",
        "title": "Disk I/O Saturation and High IOPS Wait Times",
        "failure_domain": "infrastructure",
        "symptoms": "Disk I/O utilization at 98% with high IOPS wait. Query planner selected sequential scan over table with 12M rows. Response times degraded across cluster.",
        "steps": [
            "1. Run `iostat -xz 1` to observe disk queue lengths and await metrics.",
            "2. Identify heavy query causing sequential scan in PostgreSQL `pg_stat_statements`.",
            "3. Create missing index concurrently: `CREATE INDEX CONCURRENTLY idx_tenant_created ON orders(tenant_id, created_at);`",
            "4. Verify IOPS utilization drops below 40%.",
        ],
        "tags": ["disk", "iops", "io_wait", "sequential_scan", "index"],
    },
]
