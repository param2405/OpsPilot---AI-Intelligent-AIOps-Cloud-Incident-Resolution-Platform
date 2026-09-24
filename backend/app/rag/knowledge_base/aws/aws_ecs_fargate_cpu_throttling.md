# AWS Operational Guide: ECS Fargate CPU Throttling and Memory Pressure

## Overview & Performance Bottlenecks
AWS ECS tasks running on AWS Fargate operate under strict kernel cgroup limits. When a container consumes CPU beyond its allotted vCPU quota, the Linux Completely Fair Scheduler (CFS) throttles container CPU execution time slices, resulting in severe latency spikes and HTTP 504 timeouts.

## Detection via CloudWatch & Container Insights
1. CloudWatch Metric `CPUUtilization`: Sustained values >= 90% indicate thread pool saturation.
2. Container Insights Metric `CpuReserved` vs `CpuUtilized`:
   - If `CpuUtilized` consistently matches `CpuReserved`, the container is being hard-throttled by CFS quotas.
3. Thread Starvation Symptoms:
   - Synchronous network calls take 5x to 10x longer despite external services responding normally.
   - Garbage collector execution time spikes due to CPU starvation during STW phases.

## Immediate Remediation Steps

### Action 1: Scale Task Count Out
Alleviate per-task CPU load immediately by increasing desired task count:
```bash
aws ecs update-service \
    --cluster opspilot-production-ecs \
    --service order-service-worker \
    --desired-count 12 \
    --region us-east-1
```

### Action 2: Update Task Definition vCPU and Memory Allocations
If CPU demand is intrinsically high per task (e.g. heavy serialization or compression):
1. Create a new task definition revision doubling resource specs:
   - CPU: `2048` (2 vCPU) -> `4096` (4 vCPU)
   - Memory: `4096` (4 GB) -> `8192` (8 GB)
2. Deploy the new task definition revision:
   ```bash
   aws ecs update-service \
       --cluster opspilot-production-ecs \
       --service order-service-worker \
       --task-definition order-service-worker:24 \
       --force-new-deployment \
       --region us-east-1
   ```

### Action 3: Configure Target Tracking Autoscaling
Prevent future throttling incidents by registering an Application Auto Scaling target:
```bash
aws application-autoscaling put-scaling-policy \
    --policy-name ecs-cpu-target-tracking-70 \
    --service-namespace ecs \
    --resource-id service/opspilot-production-ecs/order-service-worker \
    --scalable-dimension ecs:service:DesiredCount \
    --policy-type TargetTrackingScaling \
    --target-tracking-scaling-policy-configuration file://autoscaling-cpu-config.json
```
Target tracking configuration:
- `TargetValue: 70.0`
- `ScaleInCooldown: 300`
- `ScaleOutCooldown: 60`
