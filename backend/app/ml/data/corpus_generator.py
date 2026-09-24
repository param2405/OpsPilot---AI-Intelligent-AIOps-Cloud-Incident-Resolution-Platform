"""Historical Incident Corpus Generator for OpsPilot AI.

Synthesizes a reproducible, high-fidelity historical incident corpus (1,200 records)
with authentic SRE postmortem descriptions, telemetry metrics at onset,
and ground-truth labels across 6 failure domains and 4 severity tiers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random
from typing import Any, Dict, List
import pandas as pd


CATEGORIES = [
    "database",
    "application",
    "infrastructure",
    "network",
    "deployment",
    "external_dependency",
]

SEVERITIES = [
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
]

SERVICES = [
    {"id": "api-gateway", "tier": "critical"},
    {"id": "auth-service", "tier": "critical"},
    {"id": "order-service", "tier": "critical"},
    {"id": "payment-service", "tier": "critical"},
    {"id": "inventory-service", "tier": "high"},
    {"id": "notification-service", "tier": "standard"},
]

# Domain-specific templates for realistic SRE symptoms and root causes
DOMAIN_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "database": [
        {
            "title": "PostgreSQL Connection Pool Exhaustion in {service}",
            "symptoms": "HikariCP connection pool timeout waiting for connection. Active DB connections reached 100/100 cap. Queries queued and timed out after 5000ms. Error rate spiked on database transactions.",
            "root_cause": "Unclosed transaction in batch processor caused connection leaks. Orphaned sessions held table locks indefinitely.",
        },
        {
            "title": "Deadlock and Row Lock Contention on Orders Table",
            "symptoms": "Postgres ERROR: deadlock detected between process 14023 and 14029. Multiple concurrent transactions updating same account balance rows concurrently. Response latency degraded severely.",
            "root_cause": "Inconsistent lock ordering across distributed checkout and inventory deduction routines.",
        },
        {
            "title": "Database Sequential Table Scan Causing High I/O Wait",
            "symptoms": "Query execution time jumped from 15ms to 4200ms. Disk I/O utilization at 98% with high IOPS wait. Query planner selected sequential scan over table with 12M rows.",
            "root_cause": "Missing composite index on tenant_id and created_at columns after schema modification.",
        },
        {
            "title": "Read Replica Replication Lag Exceeding Threshold in {service}",
            "symptoms": "Replication lag on follower DB node climbed past 180 seconds. Client queries reading stale state and returning HTTP 409 conflict errors.",
            "root_cause": "Heavy analytical query executing on primary replica saturated write-ahead log (WAL) sender process.",
        },
    ],
    "application": [
        {
            "title": "JVM Heap Exhaustion and OutOfMemoryError in {service}",
            "symptoms": "Memory usage steadily climbed to 98% over 3 hours. Severe garbage collection pauses (Stop-The-World GC > 4000ms). Container terminated with exit code 137 (SIGKILL).",
            "root_cause": "Unbounded in-memory caching of deserialized JSON payloads without TTL or eviction policy.",
        },
        {
            "title": "Catastrophic Regex Backtracking and CPU Starvation",
            "symptoms": "CPU usage pegged at 100% across all worker threads. Service failed liveness probes. p95 latency skyrocketed from 25ms to 2800ms.",
            "root_cause": "Vulnerable regular expression in input validation evaluated exponentially on malformed authorization headers.",
        },
        {
            "title": "Worker Thread Pool Saturation and Task Rejection in {service}",
            "symptoms": "ThreadPoolExecutor rejected tasks with RejectedExecutionException. Queue size exceeded capacity of 1000 tasks. Requests failing with HTTP 503 Service Unavailable.",
            "root_cause": "Synchronous blocking I/O calls inside event-loop handlers prevented worker thread yield.",
        },
        {
            "title": "Uncaught NullPointerException in Request Pipeline",
            "symptoms": "Sudden spike in HTTP 500 Internal Server Errors. Log stream saturated with NullPointerException stack traces across microservice endpoints.",
            "root_cause": "Missing null check when parsing optional metadata payload in incoming request headers.",
        },
    ],
    "infrastructure": [
        {
            "title": "Ephemeral Disk Volume Space Exhaustion on {service} Node",
            "symptoms": "Root filesystem reached 100% disk usage. Application unable to write temporary files or logs. Pod entered CrashLoopBackOff state.",
            "root_cause": "Log rotation failure on access logs directory coupled with rapid debug logging output.",
        },
        {
            "title": "Kubernetes Node Eviction Due to Memory Pressure",
            "symptoms": "Kubelet triggered pod eviction on worker node. Multiple service instances terminated simultaneously leading to capacity degradation.",
            "root_cause": "Under-provisioned cgroup memory limits allowed neighboring co-located batch container to consume node memory.",
        },
        {
            "title": "CPU Throttling via CFS Cgroup Quota in {service}",
            "symptoms": "p99 latency degraded 10x while host CPU usage appeared low. cgroup stats show 45% throttling of container CPU quota slices.",
            "root_cause": "Container CPU limits set too aggressively low relative to bursty incoming request volume.",
        },
        {
            "title": "Kernel OOM Killer Invoked on Service Host",
            "symptoms": "Kernel message: Out of memory: Kill process 8912 (python) score 852 or sacrifice child. Service instance suddenly dropped offline.",
            "root_cause": "High memory consumption during massive batch file processing triggered Linux kernel page cache exhaustion.",
        },
    ],
    "network": [
        {
            "title": "Packet Loss and TCP Socket Retransmissions on {service}",
            "symptoms": "TCP socket timeout rate elevated to 16%. Network throughput dropped by 70%. Inter-service gRPC calls failing with DEADLINE_EXCEEDED.",
            "root_cause": "Network interface MTU mismatch causing IP packet fragmentation and black-hole packet drops at gateway ENI.",
        },
        {
            "title": "CoreDNS Intermittent Resolution Timeouts",
            "symptoms": "Intermittent DNS lookup failures: EAI_AGAIN or dial tcp: lookup service.internal: i/o timeout. HTTP 502 Bad Gateway responses.",
            "root_cause": "DNS query rate limit exceeded on upstream Kubernetes CoreDNS pods due to lack of local nodelocaldns caching.",
        },
        {
            "title": "BGP Route Flapping and Gateway Connection Resets",
            "symptoms": "Connection reset by peer errors (ECONNRESET) across ingress traffic. Latency variance increased by 400ms.",
            "root_cause": "Unstable upstream ISP BGP peering link caused repeated routing table reconvergence cycles.",
        },
        {
            "title": "NAT Gateway Port Exhaustion During High Egress Load",
            "symptoms": "External HTTPS requests failing with connection timeout. AWS CloudWatch NATGateway ErrorPortAllocation metric peaked.",
            "root_cause": "High volume of short-lived outbound API calls exhausted TCP ephemeral source ports on egress NAT gateway.",
        },
    ],
    "deployment": [
        {
            "title": "Missing Environment Configuration Secret Following Release v2.4.0",
            "symptoms": "Immediate spike in HTTP 500 responses immediately following deployment. Application crashed with KeyError: STRIPE_WEBHOOK_SECRET_KEY.",
            "root_cause": "Deployment manifest rolled out without corresponding secret manager binding in production namespace.",
        },
        {
            "title": "Database Schema Migration Incompatibility During Rolling Update",
            "symptoms": "Old service version pods still handling traffic encountered ColumnDoesNotExist exception following alter table migration.",
            "root_cause": "Non-backward-compatible database migration applied before old application versions were fully drained.",
        },
        {
            "title": "Defective Canary Release Rollout With Memory Regression",
            "symptoms": "Canary version pods consuming 4x memory of baseline pods. Error rate on canary traffic jumped to 34%.",
            "root_cause": "Unoptimized dependency upgrade included unindexed caching layer in new release candidate.",
        },
        {
            "title": "Incorrect Ingress Routing Rules Rollout in {service}",
            "symptoms": "All traffic to /api/v1/checkout routed to 404 Not Found. Traffic routing completely disrupted post deployment.",
            "root_cause": "Syntax error in path prefix regex in ingress controller Helm template during CI/CD deploy.",
        },
    ],
    "external_dependency": [
        {
            "title": "Third-Party Payment Gateway 503 Outage in {service}",
            "symptoms": "Checkout credit card authorization failed with 85% error rate. Upstream acquirer returned HTTP 503 Service Unavailable.",
            "root_cause": "Unannounced maintenance downtime on external payment processor authorization API.",
        },
        {
            "title": "Cloud Object Storage S3 Rate Limit and 503 SlowDown",
            "symptoms": "Image and invoice uploads failing with SlowDown: Please reduce your request rate. Elevated latency on object storage calls.",
            "root_cause": "Single S3 prefix received over 5500 PUT requests per second without hash partition prefixing.",
        },
        {
            "title": "Third-Party SMS/Email Notification Gateway Degradation",
            "symptoms": "Outgoing SMS messages queued indefinitely. Provider response latency spiked to 12,000ms before returning 504 Gateway Timeout.",
            "root_cause": "Global carrier delivery outage at third-party communications vendor.",
        },
        {
            "title": "External OAuth2 Identity Provider Failure",
            "symptoms": "Single Sign-On login attempts failing with OAuth2 token exchange timeout. User authentication completely blocked.",
            "root_cause": "Upstream IdP provider suffered major regional outage affecting identity token validation endpoints.",
        },
    ],
}


class HistoricalIncidentCorpusGenerator:
    """Generates a balanced, realistic corpus of 1,200 historical SRE incidents for supervised ML."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_corpus(self, n_samples: int = 1200) -> pd.DataFrame:
        """Generate deterministic incident records with features and labels."""
        records: List[Dict[str, Any]] = []
        base_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Distribute samples evenly across 6 categories
        samples_per_cat = n_samples // len(CATEGORIES)

        for cat in CATEGORIES:
            templates = DOMAIN_TEMPLATES[cat]
            for i in range(samples_per_cat):
                svc = self.rng.choice(SERVICES)
                template = self.rng.choice(templates)
                
                # Determine realistic severity based on category and service tier
                # Critical services or severe failure modes have higher probability of CRITICAL/HIGH
                sev_weights = [0.15, 0.25, 0.35, 0.25] if svc["tier"] == "critical" else [0.35, 0.35, 0.20, 0.10]
                severity = self.rng.choices(SEVERITIES, weights=sev_weights, k=1)[0]

                # Format strings
                title = template["title"].format(service=svc["id"])
                symptoms = template["symptoms"]
                root_cause = template["root_cause"]

                # Generate correlated onset telemetry metrics
                cpu = self.rng.uniform(15.0, 45.0)
                mem = self.rng.uniform(30.0, 60.0)
                disk = self.rng.uniform(35.0, 55.0)
                net = self.rng.uniform(200.0, 1500.0)
                req_count = self.rng.randint(100, 1200)
                lat_p95 = self.rng.uniform(20.0, 60.0)
                err_rate = self.rng.uniform(0.0005, 0.005)
                active_conns = self.rng.randint(10, 40)

                # Perturb metrics according to category and severity
                intensity = {"LOW": 0.3, "MEDIUM": 0.6, "HIGH": 0.9, "CRITICAL": 1.4}[severity]

                if cat == "database":
                    active_conns = int(active_conns + 60 * intensity)
                    lat_p95 += 1500 * intensity
                    err_rate += 0.25 * intensity
                elif cat == "application":
                    if "Heap" in title or "Memory" in title:
                        mem = min(100.0, mem + 50 * intensity)
                    else:
                        cpu = min(100.0, cpu + 55 * intensity)
                    lat_p95 += 800 * intensity
                    err_rate += 0.15 * intensity
                elif cat == "infrastructure":
                    if "Disk" in title:
                        disk = min(100.0, disk + 50 * intensity)
                    else:
                        cpu = min(100.0, cpu + 60 * intensity)
                    err_rate += 0.10 * intensity
                elif cat == "network":
                    net = max(10.0, net * (1.0 - 0.7 * min(1.0, intensity)))
                    lat_p95 += 1200 * intensity
                    err_rate += 0.20 * intensity
                elif cat == "deployment":
                    err_rate += 0.45 * intensity
                    lat_p95 += 300 * intensity
                elif cat == "external_dependency":
                    err_rate += 0.65 * intensity
                    lat_p95 += 2000 * intensity
                    cpu = max(5.0, cpu - 10.0)  # low CPU during external wait

                # Clamp bounds
                cpu = round(min(100.0, max(1.0, cpu)), 2)
                mem = round(min(100.0, max(1.0, mem)), 2)
                disk = round(min(100.0, max(1.0, disk)), 2)
                net = round(max(0.0, net), 2)
                lat_p95 = round(max(1.0, lat_p95), 2)
                err_rate = round(min(1.0, max(0.0, err_rate)), 4)
                active_conns = max(0, active_conns)

                timestamp = base_time + timedelta(hours=i * 5 + self.rng.randint(1, 4))

                records.append({
                    "incident_id": f"HIST-INC-{cat[:3].upper()}-{i+1:04d}",
                    "service_id": svc["id"],
                    "tier": svc["tier"],
                    "timestamp": timestamp,
                    "title": title,
                    "symptoms": symptoms,
                    "root_cause": root_cause,
                    "category": cat,
                    "severity": severity,
                    "cpu_usage": cpu,
                    "memory_usage": mem,
                    "disk_usage": disk,
                    "network_traffic_kbps": net,
                    "request_count": req_count,
                    "latency_p95_ms": lat_p95,
                    "error_rate": err_rate,
                    "active_connections": active_conns,
                })

        # Shuffle deterministically
        self.rng.shuffle(records)
        return pd.DataFrame(records)
