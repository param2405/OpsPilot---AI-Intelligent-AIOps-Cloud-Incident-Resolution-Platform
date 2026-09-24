# Runbook: JVM OutOfMemoryError and GC Heap Thrashing (ERR_JVM_OOM)

## Overview & Scope
This runbook covers emergency response for Java Virtual Machine heap exhaustion, frequent Stop-the-World garbage collection pauses, and container restarts in the `payment-gateway` and `billing-worker` microservices.

## Symptoms & Alert Criteria
Alert `JvmMemoryPressureCritical` fires when:
- Logs report `java.lang.OutOfMemoryError: Java heap space` or `GC overhead limit exceeded`.
- Full GC duration exceeds 10,000ms over a 2-minute rolling window.
- JVM heap usage sustained above 90% of `-Xmx` ceiling.
- Kubernetes pod restarts with termination reason `OOMKilled` (exit code 137).

## Diagnostic Steps

### Step 1: Capture JVM Memory Statistics via JCmd
Access the problematic pod and query garbage collector memory pools:
```bash
kubectl exec -it deployment/payment-gateway -n production -- jcmd 1 GC.heap_info
kubectl exec -it deployment/payment-gateway -n production -- jstat -gcutil 1 1000 10
```

### Step 2: Extract Heap Dump to S3
If the pod is responsive and heap dump on OOM did not trigger automatically:
```bash
kubectl exec -it deployment/payment-gateway -n production -- \
    jcmd 1 GC.dump /tmp/heap_dump_$(date +%s).hprof
aws s3 cp /tmp/heap_dump_*.hprof s3://opspilot-diagnostics-production/heap-dumps/
```

### Step 3: Inspect Thread Leaks and Deadlocks
Generate a thread dump to check if worker threads are blocked allocating buffers:
```bash
kubectl exec -it deployment/payment-gateway -n production -- jcmd 1 Thread.print
```

## Remediation & Recovery

### Action 1: Emergency Container Recycling
If the instance is unresponsive or in CrashLoopBackOff:
```bash
kubectl rollout restart deployment/payment-gateway -n production
```

### Action 2: JVM Flag Tuning for Fast Failover
Ensure the JVM process immediately terminates on OOM to let Kubernetes restart the container instead of hanging in an unresponsive state:
Add the following flags to `JAVA_TOOL_OPTIONS`:
```
-XX:+ExitOnOutOfMemoryError
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/var/log/dumps/
-XX:+UseG1GC
-XX:MaxGCPauseMillis=200
-XX:InitiatingHeapOccupancyPercent=45
```

### Action 3: Pod Memory Limit Adjustment
Update the Kubernetes pod resource specification to grant adequate headroom:
```yaml
resources:
  requests:
    memory: "4Gi"
    cpu: "2000m"
  limits:
    memory: "6Gi"
    cpu: "4000m"
```
Apply the configuration update:
```bash
kubectl apply -f k8s/production/payment-gateway-deployment.yaml
```
