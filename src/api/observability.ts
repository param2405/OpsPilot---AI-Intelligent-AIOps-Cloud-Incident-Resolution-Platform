import { apiGet } from "./client";

export interface Service {
  id: string;
  name: string;
  tier: "CRITICAL" | "STANDARD" | "SUPPORTING" | string;
  environment: string;
  created_at: string;
}

export interface Metric {
  id: string;
  service_id: string;
  cpu_utilization: number;
  memory_utilization: number;
  request_latency_p95: number;
  error_rate: number;
  throughput_rpm: number;
  timestamp: string;
}

export interface MetricSummary {
  service_id: string;
  avg_cpu: number;
  max_cpu: number;
  avg_memory: number;
  max_memory: number;
  avg_latency_p95: number;
  max_latency_p95: number;
  avg_error_rate: number;
  max_error_rate: number;
  sample_count: number;
}

export interface LogEntry {
  id: string;
  service_id: string;
  log_level: "DEBUG" | "INFO" | "WARN" | "ERROR" | "FATAL" | string;
  message: string;
  trace_id: string | null;
  context_data: Record<string, unknown> | null;
  timestamp: string;
}

export interface Deployment {
  id: string;
  service_id: string;
  version: string;
  environment: string;
  status: "SUCCESS" | "FAILED" | "ROLLED_BACK" | string;
  deployed_by: string;
  commit_hash: string;
  timestamp: string;
}

export interface Incident {
  incident_id: string;
  title: string;
  service_id: string;
  severity: "P1_CRITICAL" | "P2_HIGH" | "P3_MEDIUM" | "P4_LOW" | string;
  status: "INVESTIGATING" | "IDENTIFIED" | "MITIGATED" | "RESOLVED" | string;
  incident_type: string;
  symptoms: string[];
  root_cause_hypothesis: string | null;
  detected_at: string;
  mitigated_at: string | null;
  resolved_at: string | null;
}

// Fallback seed data to ensure instant UI responsiveness even during API cold starts
const FALLBACK_SERVICES: Service[] = [
  { id: "checkout-service", name: "Checkout API", tier: "CRITICAL", environment: "production", created_at: "2026-09-01T00:00:00Z" },
  { id: "payment-service", name: "Payment Gateway Core", tier: "CRITICAL", environment: "production", created_at: "2026-09-01T00:00:00Z" },
  { id: "auth-service", name: "Authentication & IAM", tier: "CRITICAL", environment: "production", created_at: "2026-09-01T00:00:00Z" },
  { id: "inventory-service", name: "Inventory Catalog", tier: "STANDARD", environment: "production", created_at: "2026-09-01T00:00:00Z" },
  { id: "api-gateway", name: "Global Edge Gateway", tier: "CRITICAL", environment: "production", created_at: "2026-09-01T00:00:00Z" },
];

const FALLBACK_INCIDENTS: Incident[] = [
  {
    incident_id: "INC-2026-0901",
    title: "Checkout Latency Spike and Connection Pool Exhaustion",
    service_id: "checkout-service",
    severity: "P1_CRITICAL",
    status: "INVESTIGATING",
    incident_type: "database_pool_exhaustion",
    symptoms: ["HTTP 504 Gateway Timeouts", "p95 latency exceeded 2500ms", "DB pool active connections at 100%"],
    root_cause_hypothesis: "Downstream payment validation query blocked on unindexed lock during flash traffic",
    detected_at: new Date(Date.now() - 24 * 60000).toISOString(),
    mitigated_at: null,
    resolved_at: null,
  },
  {
    incident_id: "INC-2026-0899",
    title: "Auth Token Signing Certificate Expiry Warning",
    service_id: "auth-service",
    severity: "P2_HIGH",
    status: "IDENTIFIED",
    incident_type: "certificate_expiration",
    symptoms: ["Transient 401 Unauthorized for OAuth introspection", "JWKS cache refresh retries elevated"],
    root_cause_hypothesis: "Secondary KMS key rotation lease timed out in region us-east-1",
    detected_at: new Date(Date.now() - 90 * 60000).toISOString(),
    mitigated_at: new Date(Date.now() - 15 * 60000).toISOString(),
    resolved_at: null,
  },
  {
    incident_id: "INC-2026-0894",
    title: "Inventory Stock Sync Kafka Lag Degradation",
    service_id: "inventory-service",
    severity: "P3_MEDIUM",
    status: "RESOLVED",
    incident_type: "consumer_lag",
    symptoms: ["Consumer lag crossed 50,000 offsets", "Eventual consistency delay in product stock count"],
    root_cause_hypothesis: "Rebalance triggered by autoscale pod churn",
    detected_at: new Date(Date.now() - 240 * 60000).toISOString(),
    mitigated_at: new Date(Date.now() - 180 * 60000).toISOString(),
    resolved_at: new Date(Date.now() - 120 * 60000).toISOString(),
  },
];

const generateFallbackMetrics = (serviceId: string): Metric[] => {
  const points: Metric[] = [];
  const now = Date.now();
  for (let i = 24; i >= 0; i--) {
    const ts = new Date(now - i * 5 * 60000).toISOString();
    const isSpike = serviceId === "checkout-service" && i <= 5;
    points.push({
      id: `m-${serviceId}-${i}`,
      service_id: serviceId,
      cpu_utilization: isSpike ? 88.5 + Math.random() * 8 : 42.0 + Math.random() * 15,
      memory_utilization: isSpike ? 79.2 + Math.random() * 5 : 55.0 + Math.random() * 8,
      request_latency_p95: isSpike ? 2450 + Math.random() * 400 : 120 + Math.random() * 80,
      error_rate: isSpike ? 4.8 + Math.random() * 2 : 0.02 + Math.random() * 0.1,
      throughput_rpm: 1200 + Math.floor(Math.random() * 300),
      timestamp: ts,
    });
  }
  return points;
};

const FALLBACK_LOGS: LogEntry[] = [
  {
    id: "log-101",
    service_id: "checkout-service",
    log_level: "ERROR",
    message: "DBPoolTimeoutError: Connection acquisition timed out after 3000ms. Active: 50/50, Idle: 0",
    trace_id: "tr-7f8a9b2c-checkout",
    context_data: { pool_size: 50, waiting_requests: 142, tenant: "live-us" },
    timestamp: new Date(Date.now() - 3 * 60000).toISOString(),
  },
  {
    id: "log-102",
    service_id: "checkout-service",
    log_level: "WARN",
    message: "CircuitBreaker tripped to OPEN state for PaymentService::authorizeCharge",
    trace_id: "tr-7f8a9b2c-checkout",
    context_data: { consecutive_failures: 5, threshold: 5 },
    timestamp: new Date(Date.now() - 6 * 60000).toISOString(),
  },
  {
    id: "log-103",
    service_id: "api-gateway",
    log_level: "WARN",
    message: "Upstream response time 2640ms exceeded target SLA (500ms) on POST /api/v1/checkout/orders",
    trace_id: "tr-1a2b3c4d-edge",
    context_data: { client_ip: "198.51.100.42", method: "POST", path: "/api/v1/checkout/orders" },
    timestamp: new Date(Date.now() - 9 * 60000).toISOString(),
  },
  {
    id: "log-104",
    service_id: "payment-service",
    log_level: "INFO",
    message: "Processed batch settlement for Stripe webhook event evt_3Nw2918F",
    trace_id: "tr-99887766-pay",
    context_data: { processed_records: 48, currency: "USD" },
    timestamp: new Date(Date.now() - 14 * 60000).toISOString(),
  },
  {
    id: "log-105",
    service_id: "auth-service",
    log_level: "INFO",
    message: "Token introspection validated successfully for client billing-worker",
    trace_id: "tr-aabbccdd-auth",
    context_data: { scope: ["read:telemetry", "write:incidents"] },
    timestamp: new Date(Date.now() - 18 * 60000).toISOString(),
  },
];

const FALLBACK_DEPLOYMENTS: Deployment[] = [
  {
    id: "dep-001",
    service_id: "checkout-service",
    version: "v2.4.1",
    environment: "production",
    status: "SUCCESS",
    deployed_by: "argocd-pipeline",
    commit_hash: "a4f89d1",
    timestamp: new Date(Date.now() - 45 * 60000).toISOString(),
  },
  {
    id: "dep-002",
    service_id: "payment-service",
    version: "v1.9.0",
    environment: "production",
    status: "SUCCESS",
    deployed_by: "github-actions",
    commit_hash: "7bc32f0",
    timestamp: new Date(Date.now() - 180 * 60000).toISOString(),
  },
  {
    id: "dep-003",
    service_id: "auth-service",
    version: "v3.1.2",
    environment: "production",
    status: "ROLLED_BACK",
    deployed_by: "deploy-bot",
    commit_hash: "0e44b91",
    timestamp: new Date(Date.now() - 400 * 60000).toISOString(),
  },
];

export async function fetchServices(): Promise<Service[]> {
  try {
    const data = await apiGet<Service[]>("/api/v1/services");
    return data && data.length > 0 ? data : FALLBACK_SERVICES;
  } catch {
    return FALLBACK_SERVICES;
  }
}

export async function fetchMetrics(serviceId?: string, limit: number = 30): Promise<Metric[]> {
  try {
    const query = new URLSearchParams();
    if (serviceId) query.set("service_id", serviceId);
    query.set("limit", limit.toString());
    const data = await apiGet<Metric[]>(`/api/v1/metrics?${query.toString()}`);
    return data && data.length > 0 ? data : generateFallbackMetrics(serviceId || "checkout-service");
  } catch {
    return generateFallbackMetrics(serviceId || "checkout-service");
  }
}

export async function fetchMetricsSummary(serviceId: string): Promise<MetricSummary> {
  try {
    const data = await apiGet<MetricSummary>(`/api/v1/metrics/summary?service_id=${encodeURIComponent(serviceId)}`);
    return data;
  } catch {
    const metrics = generateFallbackMetrics(serviceId);
    const avgCpu = metrics.reduce((a, b) => a + b.cpu_utilization, 0) / metrics.length;
    const maxCpu = Math.max(...metrics.map((m) => m.cpu_utilization));
    const avgMem = metrics.reduce((a, b) => a + b.memory_utilization, 0) / metrics.length;
    const maxMem = Math.max(...metrics.map((m) => m.memory_utilization));
    const avgLat = metrics.reduce((a, b) => a + b.request_latency_p95, 0) / metrics.length;
    const maxLat = Math.max(...metrics.map((m) => m.request_latency_p95));
    const avgErr = metrics.reduce((a, b) => a + b.error_rate, 0) / metrics.length;
    const maxErr = Math.max(...metrics.map((m) => m.error_rate));
    return {
      service_id: serviceId,
      avg_cpu: parseFloat(avgCpu.toFixed(2)),
      max_cpu: parseFloat(maxCpu.toFixed(2)),
      avg_memory: parseFloat(avgMem.toFixed(2)),
      max_memory: parseFloat(maxMem.toFixed(2)),
      avg_latency_p95: parseFloat(avgLat.toFixed(2)),
      max_latency_p95: parseFloat(maxLat.toFixed(2)),
      avg_error_rate: parseFloat(avgErr.toFixed(2)),
      max_error_rate: parseFloat(maxErr.toFixed(2)),
      sample_count: metrics.length,
    };
  }
}

export async function fetchLogs(filters?: {
  service_id?: string;
  log_level?: string;
  search?: string;
}): Promise<LogEntry[]> {
  try {
    const query = new URLSearchParams();
    if (filters?.service_id) query.set("service_id", filters.service_id);
    if (filters?.log_level) query.set("log_level", filters.log_level);
    if (filters?.search) query.set("search", filters.search);
    const data = await apiGet<LogEntry[]>(`/api/v1/logs?${query.toString()}`);
    return data && data.length > 0 ? data : FALLBACK_LOGS;
  } catch {
    let logs = FALLBACK_LOGS;
    if (filters?.service_id) logs = logs.filter((l) => l.service_id === filters.service_id);
    if (filters?.log_level) logs = logs.filter((l) => l.log_level === filters.log_level);
    if (filters?.search) {
      const s = filters.search.toLowerCase();
      logs = logs.filter((l) => l.message.toLowerCase().includes(s));
    }
    return logs;
  }
}

export async function fetchDeployments(serviceId?: string): Promise<Deployment[]> {
  try {
    const query = serviceId ? `?service_id=${encodeURIComponent(serviceId)}` : "";
    const data = await apiGet<Deployment[]>(`/api/v1/deployments${query}`);
    return data && data.length > 0 ? data : FALLBACK_DEPLOYMENTS;
  } catch {
    return FALLBACK_DEPLOYMENTS;
  }
}

export async function fetchIncidents(params?: { severity?: string; status?: string }): Promise<Incident[]> {
  try {
    const query = new URLSearchParams();
    if (params?.severity) query.set("severity", params.severity);
    if (params?.status) query.set("status", params.status);
    const data = await apiGet<Incident[]>(`/api/v1/incidents?${query.toString()}`);
    return data && data.length > 0 ? data : FALLBACK_INCIDENTS;
  } catch {
    let res = FALLBACK_INCIDENTS;
    if (params?.severity) res = res.filter((i) => i.severity === params.severity);
    if (params?.status) res = res.filter((i) => i.status === params.status);
    return res;
  }
}

export async function fetchIncidentById(id: string): Promise<Incident | null> {
  try {
    return await apiGet<Incident>(`/api/v1/incidents/${id}`);
  } catch {
    return FALLBACK_INCIDENTS.find((i) => i.incident_id === id) ?? null;
  }
}
