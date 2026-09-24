"""Curated golden evaluation dataset for OpsPilot RAG benchmarking across 6 domains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class EvalSample:
    """Evaluation benchmark sample."""

    id: str
    domain: str
    question: str
    expected_source: Optional[str]  # None for out-of-domain unanswerable queries
    expected_information: List[str]
    is_answerable: bool = True


EVALUATION_DATASET: List[EvalSample] = [
    # 1. Runbooks
    EvalSample(
        id="eval_rb_01",
        domain="runbooks",
        question="How do I identify and terminate idle in transaction sessions causing PostgreSQL pool exhaustion?",
        expected_source="doc_rb_pg_pool_exhaustion",
        expected_information=[
            "idle in transaction",
            "pg_stat_activity",
            "pg_terminate_backend",
            "state_change",
        ],
    ),
    EvalSample(
        id="eval_rb_02",
        domain="runbooks",
        question="What JVM flags should be configured to terminate immediately and generate a heap dump upon OutOfMemoryError?",
        expected_source="doc_rb_jvm_oom_recovery",
        expected_information=[
            "-XX:+ExitOnOutOfMemoryError",
            "-XX:+HeapDumpOnOutOfMemoryError",
            "HeapDumpPath",
            "G1GC",
        ],
    ),
    # 2. Architecture
    EvalSample(
        id="eval_arch_01",
        domain="architecture",
        question="What is the partition count and data retention policy for the raw-telemetry Kafka topic in OpsPilot?",
        expected_source="doc_arch_opspilot_topology",
        expected_information=[
            "raw-telemetry",
            "16 partitions",
            "7 days",
            "tenant_id",
        ],
    ),
    EvalSample(
        id="eval_arch_02",
        domain="architecture",
        question="What are the rate limiting thresholds enforced by the Kong API Gateway per IP and per tenant?",
        expected_source="doc_arch_gateway_routing",
        expected_information=[
            "10,000",
            "5,000",
            "Redis",
            "token-bucket",
        ],
    ),
    # 3. Deployment
    EvalSample(
        id="eval_deploy_01",
        domain="deployment",
        question="What Prometheus error rate threshold causes an Argo Rollouts canary deployment to abort?",
        expected_source="doc_deploy_k8s_canary_rollback",
        expected_information=[
            "http_requests_total",
            "1.0",
            "5xx",
            "abort",
        ],
    ),
    EvalSample(
        id="eval_deploy_02",
        domain="deployment",
        question="What stabilization window is configured for HPA scale down to prevent pod flapping?",
        expected_source="doc_deploy_hpa_scaling_policy",
        expected_information=[
            "stabilizationWindowSeconds",
            "300",
            "scaleDown",
            "75%",
        ],
    ),
    # 4. AWS Operational
    EvalSample(
        id="eval_aws_01",
        domain="aws",
        question="How do you execute an intentional manual failover on Amazon Aurora PostgreSQL using the AWS CLI?",
        expected_source="doc_aws_rds_aurora_failover",
        expected_information=[
            "aws rds failover-db-cluster",
            "aurora-pg-replica-1",
            "Tier 0",
            "AuroraReplicaLag",
        ],
    ),
    EvalSample(
        id="eval_aws_02",
        domain="aws",
        question="How is CPU throttling detected on AWS ECS Fargate and what command scales out desired task count?",
        expected_source="doc_aws_ecs_fargate_cpu_throttling",
        expected_information=[
            "CPUUtilization",
            "CFS",
            "aws ecs update-service",
            "desired-count",
        ],
    ),
    # 5. Database Troubleshooting
    EvalSample(
        id="eval_db_01",
        domain="database",
        question="What is the difference between pg_cancel_backend and pg_terminate_backend when resolving database lock contention?",
        expected_source="doc_db_postgres_lock_contention",
        expected_information=[
            "pg_cancel_backend",
            "pg_terminate_backend",
            "SIGINT",
            "SIGTERM",
        ],
    ),
    EvalSample(
        id="eval_db_02",
        domain="database",
        question="When is table bloat considered critical in PostgreSQL and how do you vacuum dead tuples without an exclusive lock?",
        expected_source="doc_db_postgres_autovacuum_tuning",
        expected_information=[
            "20%",
            "dead_tuple_pct",
            "VACUUM (PARALLEL",
            "REINDEX TABLE CONCURRENTLY",
        ],
    ),
    # 6. Historical Incidents
    EvalSample(
        id="eval_inc_01",
        domain="incidents",
        question="What was the root cause of the March 14, 2026 payment gateway cascading timeout outage?",
        expected_source="doc_inc_2026_03_payment_gateway_outage",
        expected_information=[
            "AcquirerX",
            "connect and read timeout",
            "thread pool",
            "HikariCP",
        ],
    ),
    EvalSample(
        id="eval_inc_02",
        domain="incidents",
        question="Why did the Kafka consumer experience a rebalance storm on May 22, 2026 and how was max.poll.interval.ms tuned?",
        expected_source="doc_inc_2026_05_kafka_consumer_lag_spike",
        expected_information=[
            "Stop-the-World",
            "max.poll.interval.ms",
            "600,000ms",
            "CooperativeStickyAssignor",
        ],
    ),
    # Negative Test (Unanswerable / Out of Domain)
    EvalSample(
        id="eval_neg_01",
        domain="unanswerable",
        question="How do you configure quantum key distribution teleportation on Azure Quantum Kubernetes?",
        expected_source=None,
        expected_information=[],
        is_answerable=False,
    ),
]
