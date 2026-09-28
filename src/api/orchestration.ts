/**
 * Phase 7/8 Incident Orchestration API Client.
 * Interfaces directly with /api/v1/orchestration endpoints.
 */

import { apiGet, apiPost } from "./client";

export interface DLLogAnalysis {
  is_anomaly: boolean;
  anomaly_probability: number;
  predicted_class: number;
  sequence_length: number;
  top_trigger_event: {
    index: number;
    log_message: string;
    event_id: string;
    attention_weight: number;
  } | null;
  event_tokens: string[];
  attention_weights: number[];
  latency_ms: number;
}

export interface EvidenceItem {
  category: string;
  source: string;
  description: string;
  severity_contribution: string;
}

export interface HistoricalMatch {
  incident_id: string;
  title: string;
  severity: string;
  service: string;
  root_cause_summary: string;
  resolution: string;
  similarity_score: number;
  occurred_at?: string | null;
}

export interface RemediationStep {
  step_number: number;
  action: string;
  command_or_config?: string | null;
  risk_level: string;
  source_reference?: string | null;
}

export interface SourceItem {
  title: string;
  source_type: string;
  reference_id: string;
  section?: string | null;
}

export interface IncidentInvestigationResponse {
  incident_id: string;
  investigation_id: string;
  service_id: string;
  status: "COMPLETED" | "INSUFFICIENT_EVIDENCE" | "DEGRADED" | "NORMAL" | "FAILED";
  detected_anomaly: boolean;
  anomaly_score: number;
  anomaly_details?: {
    contributing_signals?: string[];
    model_version?: string;
    algorithm?: string;
    [key: string]: unknown;
  } | null;
  predicted_category: string;
  category_confidence: number;
  category_probabilities?: Record<string, number> | null;
  predicted_severity: string;
  severity_confidence: number;
  risk_factors?: string[] | null;
  dl_log_analysis?: DLLogAnalysis | null;
  suspected_root_cause: string;
  confidence: number;
  evidence: EvidenceItem[];
  similar_incidents: HistoricalMatch[];
  retrieved_sources: SourceItem[];
  recommended_remediation: RemediationStep[];
  timeline: string[];
  degraded_components: string[];
  created_at: string;
  updated_at: string;
}

export interface InvestigationSummary {
  investigation_id: string;
  incident_id: string;
  service_id: string;
  status: string;
  detected_anomaly: boolean;
  anomaly_score: number;
  predicted_category: string;
  predicted_severity: string;
  suspected_root_cause: string;
  confidence: number;
  degraded_components: string[];
  created_at: string;
}

export interface PipelineComponentHealth {
  name: string;
  status: "READY" | "DEGRADED" | "UNAVAILABLE";
  version?: string | null;
  details?: string | null;
}

export interface PipelineHealthStatusResponse {
  pipeline_status: "HEALTHY" | "DEGRADED" | "CRITICAL";
  components: Record<string, PipelineComponentHealth>;
  timestamp: string;
}

export interface TelemetryIngestPayload {
  service_id: string;
  timestamp?: string;
  cpu_usage: number;
  memory_usage: number;
  disk_usage?: number;
  network_traffic_kbps?: number;
  request_count?: number;
  latency_p95_ms: number;
  error_rate: number;
  active_connections: number;
  recent_logs?: string[];
  incident_id?: string;
  title?: string;
  description?: string;
  anomaly_threshold?: number;
  force_investigation?: boolean;
}

/**
 * Ingest live telemetry and run the full 12-step incident orchestration pipeline.
 */
export async function processTelemetry(
  payload: TelemetryIngestPayload,
  signal?: AbortSignal
): Promise<IncidentInvestigationResponse> {
  return apiPost<IncidentInvestigationResponse>("/api/v1/orchestration/process-telemetry", payload, signal);
}

/**
 * Trigger full orchestration on an existing incident.
 */
export async function investigateIncident(
  incidentId: string,
  timeRange = "1h",
  recentLogs?: string[],
  signal?: AbortSignal
): Promise<IncidentInvestigationResponse> {
  return apiPost<IncidentInvestigationResponse>(
    "/api/v1/orchestration/investigate",
    {
      incident_id: incidentId,
      time_range: timeRange,
      recent_logs: recentLogs,
    },
    signal
  );
}

/**
 * Retrieve full investigation result by incident ID or investigation ID.
 */
export async function getInvestigationById(
  id: string,
  signal?: AbortSignal
): Promise<IncidentInvestigationResponse> {
  return apiGet<IncidentInvestigationResponse>(`/api/v1/orchestration/investigations/${id}`, signal);
}

/**
 * List recent investigations with optional filtering.
 */
export async function listInvestigations(
  params?: { service_id?: string; status?: string; limit?: number },
  signal?: AbortSignal
): Promise<InvestigationSummary[]> {
  const query = new URLSearchParams();
  if (params?.service_id) query.set("service_id", params.service_id);
  if (params?.status) query.set("status", params.status);
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString() ? `?${query.toString()}` : "";
  return apiGet<InvestigationSummary[]>(`/api/v1/orchestration/investigations${qs}`, signal);
}

/**
 * Retrieve pipeline health status across ML, DL, Agent, and RAG components.
 */
export async function getPipelineHealth(
  signal?: AbortSignal
): Promise<PipelineHealthStatusResponse> {
  return apiGet<PipelineHealthStatusResponse>("/api/v1/orchestration/pipeline/status", signal);
}
