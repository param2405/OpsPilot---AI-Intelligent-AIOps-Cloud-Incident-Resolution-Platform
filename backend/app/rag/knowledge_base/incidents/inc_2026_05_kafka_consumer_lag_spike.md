# Incident Postmortem: INC-2026-05-22 Kafka Consumer Rebalance Storm & Lag Spike

## Executive Summary
On May 22, 2026, at 08:30 UTC, the telemetry streaming pipeline suffered an 18-minute ingestion stall during morning peak traffic. Over 4.2 million telemetry metric frames were delayed, leading to temporary gaps in customer alerting dashboards.

## Impact & Severity
- Severity: P2 - Major
- Affected Services: `event-processor`, `kafka-cluster-production`, `alert-manager`
- Incident Commander: Infrastructure Architect Elena Rostova

## Root Cause Analysis
During high-load ingestion, one of the `event-processor` consumer instances experienced an extended JVM Stop-the-World garbage collection pause lasting 312 seconds.

Because Kafka consumer configuration had `max.poll.interval.ms` set to the default value of 300,000ms (5 minutes), the Kafka group coordinator considered the frozen consumer dead and initiated a consumer group partition rebalance.

When the GC pause completed, the reinstated consumer attempted to rejoin the group, triggering a second rebalance. This cyclic rebalance thrashing ("rebalance storm") repeated 7 times across all 16 topic partitions, completely halting message consumption for 18 minutes while messages accumulated at 8,500 messages/sec in the Kafka brokers.

## Timeline of Events
- 08:28 UTC: Telemetry ingress traffic jumps by 340% due to enterprise customer batch sync.
- 08:30 UTC: Consumer pod-3 enters major STW GC pause (312s).
- 08:35 UTC: Group coordinator triggers rebalance; consumer group state transitions to `PreparingRebalance`.
- 08:41 UTC: PagerDuty alert `KafkaConsumerLagCritical` triggers (> 1,000,000 messages behind).
- 08:44 UTC: Operations team scales `event-processor` deployment to 16 replicas to match partition count.
- 08:48 UTC: Deployed configuration hotfix overriding `max.poll.interval.ms` and switching to cooperative sticky rebalance protocol.
- 08:52 UTC: Consumer lag completely drained; pipeline back to real-time.

## Action Items & Preventative Measures
1. [COMPLETED] Increase `max.poll.interval.ms` from 300,000ms to 600,000ms (10 minutes).
2. [COMPLETED] Reduce `max.poll.records` from 500 to 100 to ensure record batches are processed well within the poll timeout window.
3. [COMPLETED] Adopt `CooperativeStickyAssignor` partition assignment strategy to allow unaffected partitions to continue consuming during rebalances.
4. [COMPLETED] Migrate JVM garbage collector from ParallelGC to ZGC (`-XX:+UseZGC`) to reduce STW pause times below 5ms.
