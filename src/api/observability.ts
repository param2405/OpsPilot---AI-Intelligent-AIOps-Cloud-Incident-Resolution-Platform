import { apiGet } from "./client";

export interface Service {
  id: string;
  name: string;
  tier: string;
  owner_team?: string;
  environment?: string;
  created_at: string;
}

export interface Metric {
  id: string | number;
  service_id: string;
  cpu_usage: number;
  memory_usage: number;
  latency_p95_ms: number;
  error_rate: number;
  disk_usage?: number;
  network_traffic_kbps?: number;
  request_count?: number;
  active_connections?: number;
  throughput_rpm?: number;
  timestamp: string;
}

export interface MetricSummary {
  service_id: string;
  sample_count: number;
  avg_cpu_usage: number;
  max_cpu_usage: number;
  avg_memory_usage: number;
  max_memory_usage: number;
  avg_latency_p95_ms: number;
  max_latency_p95_ms: number;
  avg_error_rate: number;
  max_error_rate: number;
}

export interface LogEntry {
  id: string | number;
  service_id: string;
  log_level: string;
  message: string;
  trace_id: string | null;
  metadata_json?: Record<string, unknown> | null;
  context_data?: Record<string, unknown> | null;
  timestamp: string;
}

export interface Deployment {
  id: string | number;
  service_id: string;
  version: string;
  environment: string;
  status: string;
  deployed_at?: string;
  deployed_by?: string;
  commit_hash?: string;
  changelog?: string;
  timestamp?: string;
}

export interface Incident {
  id: string;
  incident_id?: string;
  title: string;
  service_id: string;
  severity: string;
  status: string;
  incident_type: string;
  symptoms: string[] | string;
  root_cause?: string;
  root_cause_hypothesis?: string | null;
  resolution?: string;
  started_at?: string;
  detected_at?: string;
  mitigated_at?: string | null;
  resolved_at?: string | null;
}

// Fallback seed data in case API is temporarily unavailable
const FALLBACK_SERVICES: Service[] = [
  { id: "api-gateway", name: "API Gateway", tier: "critical", owner_team: "platform", environment: "production", created_at: "2026-09-01T00:00:00Z" },
  { id: "auth-service", name: "Authentication Service", tier: "critical", owner_team: "identity", environment: "production", created_at: "2026-09-01T00:00:00Z" },
  { id: "order-service", name: "Order Management Service", tier: "critical", owner_team: "checkout", environment: "production", created_at: "2026-09-01T00:00:00Z" },
  { id: "payment-service", name: "Payment Processing Service", tier: "critical", owner_team: "payments", environment: "production", created_at: "2026-09-01T00:00:00Z" },
  { id: "inventory-service", name: "Inventory & Catalog Service", tier: "high", owner_team: "catalog", environment: "production", created_at: "2026-09-01T00:00:00Z" },
  { id: "notification-service", name: "Notification & Messaging Service", tier: "standard", owner_team: "messaging", environment: "production", created_at: "2026-09-01T00:00:00Z" },
];

const FALLBACK_INCIDENTS: Incident[] = [
  {
    id: "INC-2026-001",
    incident_id: "INC-2026-001",
    title: "Auth Service CPU Starvation in JWT Verification Loop",
    service_id: "auth-service",
    severity: "P1_CRITICAL",
    status: "INVESTIGATING",
    incident_type: "CPU_SATURATION",
    symptoms: ["Auth service CPU pegged at 99%", "p95 latency spiked from 35ms to 1850ms", "Client token verification timeouts"],
    root_cause_hypothesis: "Catastrophic backtracking in regex claims parsing under sustained concurrent traffic",
    detected_at: new Date(Date.now() - 35 * 60000).toISOString(),
    mitigated_at: null,
    resolved_at: null,
  },
  {
    id: "INC-2026-002",
    incident_id: "INC-2026-002",
    title: "Payment Service DB Connection Pool Saturation",
    service_id: "payment-service",
    severity: "P1_CRITICAL",
    status: "IDENTIFIED",
    incident_type: "DB_CONNECTION_EXHAUSTION",
    symptoms: ["Payment processing error rate spiked to 78%", "p95 latency jumped to 5000ms timeout", "Active DB connections at 100/100 limit"],
    root_cause_hypothesis: "Missing transaction commit in idempotency verification left PostgreSQL sessions in 'idle in transaction'",
    detected_at: new Date(Date.now() - 85 * 60000).toISOString(),
    mitigated_at: new Date(Date.now() - 15 * 60000).toISOString(),
    resolved_at: null,
  },
  {
    id: "INC-2026-004",
    incident_id: "INC-2026-004",
    title: "Inventory Query Latency Spike Cascading to API Gateway",
    service_id: "inventory-service",
    severity: "P2_HIGH",
    status: "RESOLVED",
    incident_type: "API_LATENCY_SPIKE",
    symptoms: ["Inventory p95 latency degraded from 40ms to 3200ms", "API gateway queued 180 concurrent requests"],
    root_cause_hypothesis: "Sequential table scan on inventory_items due to missing composite index on (warehouse_id, sku)",
    detected_at: new Date(Date.now() - 300 * 60000).toISOString(),
    mitigated_at: new Date(Date.now() - 240 * 60000).toISOString(),
    resolved_at: new Date(Date.now() - 200 * 60000).toISOString(),
  },
];

const generateFallbackMetrics = (serviceId: string): Metric[] => {
  const points: Metric[] = [];
  const now = Date.now();
  for (let i = 24; i >= 0; i--) {
    const ts = new Date(now - i * 5 * 60000).toISOString();
    const isSpike = (serviceId === "auth-service" || serviceId === "payment-service") && i <= 5;
    points.push({
      id: `m-${serviceId}-${i}`,
      service_id: serviceId,
      cpu_usage: isSpike ? 88.5 + Math.random() * 8 : 28.0 + Math.random() * 14,
      memory_usage: isSpike ? 78.2 + Math.random() * 5 : 42.0 + Math.random() * 8,
      latency_p95_ms: isSpike ? 1850 + Math.random() * 400 : 45 + Math.random() * 25,
      error_rate: isSpike ? 0.048 + Math.random() * 0.02 : 0.001 + Math.random() * 0.001,
      disk_usage: 45.0,
      network_traffic_kbps: 180.0,
      request_count: 85,
      active_connections: 22,
      timestamp: ts,
    });
  }
  return points;
};

const FALLBACK_LOGS: LogEntry[] = [
  {
    id: "log-101",
    service_id: "payment-service",
    log_level: "ERROR",
    message: "DBPoolTimeoutError: Connection acquisition timed out after 5000ms. Active: 100/100, Idle: 0",
    trace_id: "tr-7f8a9b2c-pay",
    metadata_json: { pool_size: 100, waiting_requests: 84, db: "postgres-primary" },
    timestamp: new Date(Date.now() - 3 * 60000).toISOString(),
  },
  {
    id: "log-102",
    service_id: "auth-service",
    log_level: "ERROR",
    message: "TokenVerificationTimeout: CPU starvation during JWT RSA signature verification loop",
    trace_id: "tr-1a2b3c4d-auth",
    metadata_json: { duration_ms: 1850, claims_length: 4096 },
    timestamp: new Date(Date.now() - 7 * 60000).toISOString(),
  },
  {
    id: "log-103",
    service_id: "api-gateway",
    log_level: "WARN",
    message: "Upstream response time 1920ms exceeded target SLA (500ms) on POST /api/v1/auth/tokens",
    trace_id: "tr-1a2b3c4d-auth",
    metadata_json: { status_code: 504, client_ip: "10.212.10.42" },
    timestamp: new Date(Date.now() - 10 * 60000).toISOString(),
  },
  {
    id: "log-104",
    service_id: "inventory-service",
    log_level: "INFO",
    message: "Inventory sync batch completed successfully: 2500 skus synced in 142ms",
    trace_id: "tr-8899aabb-inv",
    metadata_json: { batch_size: 2500, warehouse_id: "us-east-wh1" },
    timestamp: new Date(Date.now() - 15 * 60000).toISOString(),
  },
];

const FALLBACK_DEPLOYMENTS: Deployment[] = [
  {
    id: "dep-001",
    service_id: "auth-service",
    version: "v2.4.1",
    environment: "production",
    status: "SUCCESS",
    deployed_by: "github-actions",
    commit_hash: "a4f89d1",
    deployed_at: new Date(Date.now() - 45 * 60000).toISOString(),
  },
  {
    id: "dep-002",
    service_id: "payment-service",
    version: "v1.9.0",
    environment: "production",
    status: "SUCCESS",
    deployed_by: "argocd",
    commit_hash: "7bc32f0",
    deployed_at: new Date(Date.now() - 180 * 60000).toISOString(),
  },
  {
    id: "dep-003",
    service_id: "order-service",
    version: "v3.1.2",
    environment: "production",
    status: "ROLLED_BACK",
    deployed_by: "deploy-bot",
    commit_hash: "0e44b91",
    deployed_at: new Date(Date.now() - 400 * 60000).toISOString(),
  },
];

export async function fetchServices(): Promise<Service[]> {
  try {
    const data = await apiGet<any[]>("/api/v1/services");
    if (Array.isArray(data) && data.length > 0) {
      return data.map((s) => ({
        id: s.id,
        name: s.name,
        tier: (s.tier ?? "standard").toUpperCase(),
        owner_team: s.owner_team,
        environment: s.environment ?? "production",
        created_at: s.created_at ?? new Date().toISOString(),
      }));
    }
    return FALLBACK_SERVICES;
  } catch {
    return FALLBACK_SERVICES;
  }
}

export async function fetchMetrics(serviceId?: string, limit: number = 30): Promise<Metric[]> {
  try {
    const query = new URLSearchParams();
    if (serviceId) query.set("service_id", serviceId);
    query.set("limit", limit.toString());
    const data = await apiGet<any[]>(`/api/v1/metrics?${query.toString()}`);
    if (Array.isArray(data) && data.length > 0) {
      return data.map((m) => ({
        id: m.id,
        service_id: m.service_id,
        cpu_usage: Number(m.cpu_usage ?? m.cpu_utilization ?? 0),
        memory_usage: Number(m.memory_usage ?? m.memory_utilization ?? 0),
        latency_p95_ms: Number(m.latency_p95_ms ?? m.request_latency_p95 ?? 0),
        error_rate: Number(m.error_rate ?? 0),
        disk_usage: Number(m.disk_usage ?? 0),
        network_traffic_kbps: Number(m.network_traffic_kbps ?? 0),
        request_count: Number(m.request_count ?? 0),
        active_connections: Number(m.active_connections ?? 0),
        timestamp: m.timestamp ?? new Date().toISOString(),
      }));
    }
    return generateFallbackMetrics(serviceId || "auth-service");
  } catch {
    return generateFallbackMetrics(serviceId || "auth-service");
  }
}

export async function fetchMetricsSummary(serviceId: string): Promise<MetricSummary> {
  try {
    const s = await apiGet<any>(`/api/v1/metrics/summary?service_id=${encodeURIComponent(serviceId)}`);
    if (s) {
      return {
        service_id: s.service_id ?? serviceId,
        sample_count: Number(s.sample_count ?? 0),
        avg_cpu_usage: Number(s.avg_cpu_usage ?? s.avg_cpu ?? 0),
        max_cpu_usage: Number(s.max_cpu_usage ?? s.max_cpu ?? 0),
        avg_memory_usage: Number(s.avg_memory_usage ?? s.avg_memory ?? 0),
        max_memory_usage: Number(s.max_memory_usage ?? s.max_memory ?? 0),
        avg_latency_p95_ms: Number(s.avg_latency_p95_ms ?? s.avg_latency_p95 ?? 0),
        max_latency_p95_ms: Number(s.max_latency_p95_ms ?? s.max_latency_p95 ?? 0),
        avg_error_rate: Number(s.avg_error_rate ?? 0),
        max_error_rate: Number(s.max_error_rate ?? 0),
      };
    }
  } catch {
    // Fall through to fallback calculation
  }

  const metrics = generateFallbackMetrics(serviceId);
  const avgCpu = metrics.reduce((a, b) => a + b.cpu_usage, 0) / metrics.length;
  const maxCpu = Math.max(...metrics.map((m) => m.cpu_usage));
  const avgMem = metrics.reduce((a, b) => a + b.memory_usage, 0) / metrics.length;
  const maxMem = Math.max(...metrics.map((m) => m.memory_usage));
  const avgLat = metrics.reduce((a, b) => a + b.latency_p95_ms, 0) / metrics.length;
  const maxLat = Math.max(...metrics.map((m) => m.latency_p95_ms));
  const avgErr = metrics.reduce((a, b) => a + b.error_rate, 0) / metrics.length;
  const maxErr = Math.max(...metrics.map((m) => m.error_rate));
  return {
    service_id: serviceId,
    sample_count: metrics.length,
    avg_cpu_usage: parseFloat(avgCpu.toFixed(2)),
    max_cpu_usage: parseFloat(maxCpu.toFixed(2)),
    avg_memory_usage: parseFloat(avgMem.toFixed(2)),
    max_memory_usage: parseFloat(maxMem.toFixed(2)),
    avg_latency_p95_ms: parseFloat(avgLat.toFixed(2)),
    max_latency_p95_ms: parseFloat(maxLat.toFixed(2)),
    avg_error_rate: parseFloat(avgErr.toFixed(4)),
    max_error_rate: parseFloat(maxErr.toFixed(4)),
  };
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
    const data = await apiGet<any[]>(`/api/v1/logs?${query.toString()}`);
    if (Array.isArray(data) && data.length > 0) {
      return data.map((l) => ({
        id: l.id,
        service_id: l.service_id,
        log_level: (l.log_level ?? "INFO").toUpperCase(),
        message: l.message ?? "",
        trace_id: l.trace_id ?? null,
        metadata_json: l.metadata_json ?? l.context_data ?? null,
        context_data: l.metadata_json ?? l.context_data ?? null,
        timestamp: l.timestamp ?? new Date().toISOString(),
      }));
    }
    return FALLBACK_LOGS;
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
    const data = await apiGet<any[]>(`/api/v1/deployments${query}`);
    if (Array.isArray(data) && data.length > 0) {
      return data.map((d) => ({
        id: d.id,
        service_id: d.service_id,
        version: d.version ?? "v1.0.0",
        environment: d.environment ?? "production",
        status: d.status ?? "SUCCESS",
        deployed_at: d.deployed_at ?? d.timestamp ?? new Date().toISOString(),
        deployed_by: d.deployed_by ?? "argocd",
        commit_hash: d.commit_hash ?? d.changelog ?? "HEAD",
        timestamp: d.deployed_at ?? d.timestamp ?? new Date().toISOString(),
      }));
    }
    return FALLBACK_DEPLOYMENTS;
  } catch {
    return FALLBACK_DEPLOYMENTS;
  }
}

export async function fetchIncidents(params?: { severity?: string; status?: string }): Promise<Incident[]> {
  try {
    const query = new URLSearchParams();
    if (params?.severity) query.set("severity", params.severity);
    if (params?.status) query.set("status", params.status);
    const data = await apiGet<any[]>(`/api/v1/incidents?${query.toString()}`);
    if (Array.isArray(data) && data.length > 0) {
      return data.map((i) => {
        let symptomsArr: string[] = [];
        if (Array.isArray(i.symptoms)) {
          symptomsArr = i.symptoms;
        } else if (typeof i.symptoms === "string") {
          symptomsArr = i.symptoms.split(";").map((s: string) => s.trim()).filter(Boolean);
        }
        return {
          id: i.id ?? i.incident_id,
          incident_id: i.id ?? i.incident_id,
          title: i.title ?? "Incident",
          service_id: i.service_id,
          severity: (i.severity ?? "P3_MEDIUM").toUpperCase(),
          status: (i.status ?? "RESOLVED").toUpperCase(),
          incident_type: i.incident_type ?? "ANOMALY",
          symptoms: symptomsArr.length > 0 ? symptomsArr : ["Anomaly detected on telemetry stream"],
          root_cause: i.root_cause,
          root_cause_hypothesis: i.root_cause ?? i.root_cause_hypothesis ?? null,
          resolution: i.resolution,
          started_at: i.started_at ?? i.detected_at,
          detected_at: i.started_at ?? i.detected_at ?? new Date().toISOString(),
          mitigated_at: i.mitigated_at ?? null,
          resolved_at: i.resolved_at ?? null,
        };
      });
    }
    return FALLBACK_INCIDENTS;
  } catch {
    let res = FALLBACK_INCIDENTS;
    if (params?.severity) res = res.filter((i) => i.severity === params.severity);
    if (params?.status) res = res.filter((i) => i.status === params.status);
    return res;
  }
}

export async function fetchIncidentById(id: string): Promise<Incident | null> {
  try {
    const incs = await fetchIncidents();
    return incs.find((i) => i.id === id || i.incident_id === id) ?? null;
  } catch {
    return FALLBACK_INCIDENTS.find((i) => i.id === id || i.incident_id === id) ?? null;
  }
}
