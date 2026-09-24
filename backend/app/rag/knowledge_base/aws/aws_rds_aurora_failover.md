# AWS Operational Guide: Amazon Aurora PostgreSQL Failover and Replica Lag

## Multi-AZ Architecture Overview
OpsPilot production databases operate on Amazon Aurora PostgreSQL Multi-AZ clusters comprising one primary read-write instance and two read-only replicas distributed across `us-east-1a`, `us-east-1b`, and `us-east-1c`.

## Failover Mechanisms & Election Priorities
Aurora failover occurs under two conditions:
1. Automated Unplanned Failover: Triggered when the primary node encounters hardware degradation, hypervisor fault, or network isolation.
2. Manual Planned Maintenance: Executed via AWS CLI or RDS Console during database engine major version upgrades.

### Promotion Tier Configuration
Replicas are assigned failover priority tiers (Tier 0 to Tier 15):
- `aurora-pg-replica-1`: Promotion Tier 0 (highest priority for failover election).
- `aurora-pg-replica-2`: Promotion Tier 1.
During failover, Aurora automatically promotes the replica in Tier 0 with the lowest replication lag. DNS CNAME records for the cluster endpoint (`*.cluster-*.rds.amazonaws.com`) update within 15 to 30 seconds.

## Managing Replica Lag & Diagnostics
Monitor Amazon CloudWatch metric `AuroraReplicaLag`.
- Normal range: < 20 milliseconds.
- Warning threshold: > 100 milliseconds.
- Critical alert: > 500 milliseconds.

Root causes of elevated replica lag:
- Heavy bulk write transactions (`COPY` or unindexed `UPDATE` batches) on the writer node.
- Long-running analytical queries on the reader instance holding snapshot locks.
- Insufficient IOPS or storage volume throttling.

## Manual Failover Execution Procedure
To initiate an intentional switchover:
```bash
aws rds failover-db-cluster \
    --db-cluster-identifier opspilot-production-aurora-cluster \
    --target-db-instance-identifier aurora-pg-replica-1 \
    --region us-east-1
```
Monitor the failover event in real-time:
```bash
aws rds describe-events \
    --source-identifier opspilot-production-aurora-cluster \
    --source-type db-cluster \
    --duration 10 \
    --region us-east-1
```

## Client Driver Fast Failover Settings
Application connection pools must enable AWS JDBC Smart Driver failover wrapper:
```properties
jdbc:aws-wrapper:postgresql://opspilot-production-aurora-cluster.cluster-xyz.us-east-1.rds.amazonaws.com:5432/opspilot
wrapperPlugins=failover,efm
failoverTimeoutMs=10000
```
This enables the client driver to detect writer failure via cluster topology queries in under 3 seconds, bypassing standard DNS cache TTL delays.
