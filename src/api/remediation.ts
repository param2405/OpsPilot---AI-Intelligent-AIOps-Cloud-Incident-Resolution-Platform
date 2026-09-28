/**
 * Phase 9: Human-In-The-Loop Remediation & Security Audit API Client
 */

import { apiGet, apiPost } from "./client";

export type RemediationActionType =
  | "restart_service"
  | "scale_service"
  | "rollback_deployment"
  | "clear_cache"
  | "toggle_circuit_breaker";

export type RemediationStatus =
  | "RECOMMENDED"
  | "APPROVED"
  | "EXECUTING"
  | "SUCCESS"
  | "FAILED"
  | "REJECTED";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export type UserRole = "VIEWER" | "OPERATOR" | "SRE_LEAD" | "PLATFORM_ADMIN" | "AI_AGENT";

export interface RemediationRecommendation {
  id: string;
  incident_id: string;
  investigation_id?: string | null;
  action_type: RemediationActionType;
  target_service: string;
  parameters: Record<string, unknown>;
  rationale: string;
  risk_level: RiskLevel;
  status: RemediationStatus;
  command_preview: string;
  runbook_reference?: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserApprovalMetadata {
  approved_by?: string;
  rejected_by?: string;
  user_role: string;
  timestamp?: string;
  comment?: string;
  rejection_reason?: string;
  approval_status: string;
}

export interface ExecutorResultSummary {
  output: string;
  execution_duration_ms: number;
  simulated: boolean;
  validation_passed: boolean;
  logs: string[];
  rollback_point?: string | null;
}

export interface RemediationAuditLog {
  id: string;
  recommendation_id?: string | null;
  incident_id: string;
  requested_action: string;
  action_parameters: Record<string, unknown>;
  simulation_mode: boolean;
  user_approval: UserApprovalMetadata;
  executor_result: ExecutorResultSummary;
  status: string;
  timestamp: string;
}

export interface ApprovalRequest {
  approved_by?: string;
  user_role?: UserRole;
  comment?: string;
}

export interface RejectRequest {
  rejected_by: string;
  user_role?: UserRole;
  rejection_reason: string;
}

export interface SimulateRemediationRequest {
  action_type: RemediationActionType;
  target_service: string;
  parameters?: Record<string, unknown>;
  operator_id?: string;
  user_role?: UserRole;
}

/**
 * Fetch all remediation recommendations with optional filters.
 */
export async function fetchRemediationRecommendations(
  incidentId?: string,
  status?: string,
  signal?: AbortSignal
): Promise<RemediationRecommendation[]> {
  const params = new URLSearchParams();
  if (incidentId) params.append("incident_id", incidentId);
  if (status) params.append("status", status);
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiGet<RemediationRecommendation[]>(`/api/v1/remediations/recommendations${query}`, signal);
}

/**
 * Fetch recommendation details by ID.
 */
export async function fetchRemediationRecommendation(
  recId: string,
  signal?: AbortSignal
): Promise<RemediationRecommendation> {
  return apiGet<RemediationRecommendation>(`/api/v1/remediations/recommendations/${encodeURIComponent(recId)}`, signal);
}

/**
 * Human approval of a recommendation executing in Safe Simulation Mode.
 */
export async function approveRemediation(
  recId: string,
  payload?: ApprovalRequest,
  signal?: AbortSignal
): Promise<RemediationRecommendation> {
  return apiPost<RemediationRecommendation>(
    `/api/v1/remediations/recommendations/${encodeURIComponent(recId)}/approve`,
    payload ?? { comment: "Approved via OpsPilot Web Console" },
    signal
  );
}

/**
 * Human rejection of a recommendation with rationale recorded to audit trail.
 */
export async function rejectRemediation(
  recId: string,
  payload: RejectRequest,
  signal?: AbortSignal
): Promise<RemediationRecommendation> {
  return apiPost<RemediationRecommendation>(
    `/api/v1/remediations/recommendations/${encodeURIComponent(recId)}/reject`,
    payload,
    signal
  );
}

/**
 * Fetch immutable remediation audit logs.
 */
export async function fetchRemediationAuditLogs(
  incidentId?: string,
  recommendationId?: string,
  signal?: AbortSignal
): Promise<RemediationAuditLog[]> {
  const params = new URLSearchParams();
  if (incidentId) params.append("incident_id", incidentId);
  if (recommendationId) params.append("recommendation_id", recommendationId);
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiGet<RemediationAuditLog[]>(`/api/v1/remediations/audit-logs${query}`, signal);
}

/**
 * Directly test an allowlisted action in Safe Simulation Mode.
 */
export async function simulateRemediationAction(
  req: SimulateRemediationRequest,
  signal?: AbortSignal
): Promise<RemediationAuditLog> {
  return apiPost<RemediationAuditLog>("/api/v1/remediations/simulate", req, signal);
}
