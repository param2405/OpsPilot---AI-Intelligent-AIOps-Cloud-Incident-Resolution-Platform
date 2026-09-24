# Deployment Standard: Kubernetes Argo Rollouts Canary and Automated Rollbacks

## Overview & Continuous Delivery Standard
All production services within the OpsPilot ecosystem utilize Argo Rollouts for progressive traffic canary deployments. Blue-green deployments are restricted to database migration workloads.

## Canary Progression Stages
Canary deployments follow a 4-phase graduated progression:
1. Phase 1 (5% traffic): 10-minute stabilization and automated Prometheus metrics analysis.
2. Phase 2 (20% traffic): 15-minute soak test with synthetic load validation.
3. Phase 3 (50% traffic): 20-minute operational evaluation.
4. Phase 4 (100% traffic): Full promotion and decommissioning of previous replica sets.

## Analysis Templates & Abort Triggers
During each canary phase, Argo Rollouts evaluates two primary Prometheus metric queries every 30 seconds:

### Metric 1: HTTP 5xx Error Rate
Query:
```promql
sum(rate(http_requests_total{status=~"5.*", app="order-service"}[2m])) 
/ 
sum(rate(http_requests_total{app="order-service"}[2m])) * 100
```
- Success condition: `result[0] <= 1.0` (Error rate must remain <= 1.0%).
- Failure limit: 3 consecutive breaches trigger an immediate rollback.

### Metric 2: P99 Latency SLA
Query:
```promql
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{app="order-service"}[2m])) by (le))
```
- Success condition: `result[0] <= 0.85` (Latency must remain <= 850ms).

## Emergency Rollback Procedures
In the event of an automated abort or manual intervention:
1. Instant Abort Command:
   ```bash
   kubectl argo rollouts abort order-service -n production
   ```
2. Rollback to Stable Revision:
   ```bash
   kubectl argo rollouts undo order-service -n production
   ```
3. Verification:
   Confirm all ingress traffic is routed 100% to the stable revision:
   ```bash
   kubectl argo rollouts get rollout order-service -n production
   ```
