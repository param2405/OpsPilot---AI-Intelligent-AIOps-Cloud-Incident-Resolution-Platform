# Incident Postmortem: INC-2026-03-14 Payment Gateway Cascading Timeout Outage

## Executive Summary
On March 14, 2026, between 14:15 UTC and 14:57 UTC (total duration: 42 minutes), the OpsPilot payment checkout service encountered a catastrophic cascade failure resulting in 99.4% failed customer transactions. An estimated 14,200 checkout attempts failed before full mitigation.

## Impact & Severity
- Severity: P1 - Critical
- Affected Services: `payment-gateway`, `order-service`, `notification-worker`
- Incident Commander: SRE Lead Marcus Vance
- Financial Impact: Estimated $180,000 in delayed transaction volume

## Root Cause Analysis
At 14:12 UTC, upstream third-party acquirer `AcquirerX` experienced internal network degradation, causing transaction authorization response times to jump from an average 180ms to over 8,500ms.

Because the `payment-gateway` HTTP client lacked an explicit connect and read timeout (relying on default indefinite TCP socket timeouts), Tomcat thread pools rapidly saturated at 400/400 active worker threads within 180 seconds.

As inbound requests queued, the upstream `order-service` synchronously waiting for `payment-gateway` responses exhausted its own HikariCP connection pool (`ERR_POOL_EXHAUSTED`), triggering a systemic domino collapse of the entire order processing pipeline.

## Timeline of Events
- 14:12 UTC: Upstream payment provider latency increases from 180ms to 8,500ms.
- 14:15 UTC: `payment-gateway` thread pool saturation alert triggers.
- 14:19 UTC: `order-service` Hikari connection pool exhausted; HTTP 503 error rate reaches 98%.
- 14:24 UTC: SRE team convenes incident war room.
- 14:31 UTC: SRE manually trips Kong API Gateway circuit breaker to divert traffic to secondary payment provider `AcquirerY`.
- 14:38 UTC: Restarted `payment-gateway` and `order-service` pods under reduced concurrency limits.
- 14:48 UTC: Error rate drops below 1.0%; latency normalizes.
- 14:57 UTC: Full system recovery verified; incident closed.

## Action Items & Preventative Measures
1. [COMPLETED] Configure mandatory 1,500ms socket read timeout on all third-party payment clients.
2. [COMPLETED] Deploy Resilience4j Circuit Breaker with automatic failover to secondary payment gateway `AcquirerY` upon 3 consecutive timeouts.
3. [COMPLETED] Implement bulkheading: isolate checkout payment execution threads from general order query threads.
4. [COMPLETED] Add synthetic canary probe testing payment partner latency every 10 seconds.
