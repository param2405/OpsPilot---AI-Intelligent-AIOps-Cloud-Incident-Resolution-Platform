# Deployment Standard: Horizontal Pod Autoscaler (HPA) and Resource Quotas

## Purpose & Autoscaling Architecture
This specification governs Horizontal Pod Autoscaling (HPA v2) behavior across all containerized workloads running on Amazon EKS clusters.

## Scaling Metrics & Target Thresholds
HPA configurations combine CPU, memory, and custom Prometheus application metrics:
- Target CPU Utilization: 75% average utilization across pod replicas.
- Target Memory Utilization: 80% working set utilization.
- Custom Metric `http_requests_per_second`: 300 requests/sec per replica for ingress services.

## Stabilization Windows & Flapping Prevention
To prevent autoscaling thrashing (rapid scale-up and scale-down cycles during transient traffic bursts), HPA enforces stabilization windows:
```yaml
behavior:
  scaleUp:
    stabilizationWindowSeconds: 0
    policies:
    - type: Percent
      value: 100
      periodSeconds: 15
    - type: Pods
      value: 4
      periodSeconds: 15
    selectPolicy: Max
  scaleDown:
    stabilizationWindowSeconds: 300
    policies:
    - type: Percent
      value: 10
      periodSeconds: 60
    selectPolicy: Min
```

## Resource Requests and Limits Standard
Every pod spec must adhere to the Guaranteed or Burstable Quality of Service (QoS) tier:
- Request-to-Limit Ratio: CPU limit must not exceed 2x CPU request. Memory limit must equal memory request to prevent unevicted page swapping under memory pressure.
- Minimum Replicas: 3 pods across 3 separate availability zones using `topologySpreadConstraints`.
- Maximum Replicas: Capped at 50 pods to prevent downstream database connection exhaustion.
