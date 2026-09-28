import { useEffect, useState } from "react";
import {
  approveRemediation,
  fetchRemediationAuditLogs,
  fetchRemediationRecommendations,
  rejectRemediation,
  RemediationActionType,
  RemediationAuditLog,
  RemediationRecommendation,
  RemediationStatus,
  simulateRemediationAction,
  UserRole,
} from "../api/remediation";
import { Badge, Card, EmptyState, LoadingSpinner } from "./common";

interface RemediationControlCenterProps {
  incidentId?: string;
  serviceId?: string;
  onIncidentUpdated?: () => void;
}

export function RemediationControlCenter({
  incidentId,
  serviceId,
  onIncidentUpdated,
}: RemediationControlCenterProps) {
  const [recommendations, setRecommendations] = useState<RemediationRecommendation[]>([]);
  const [auditLogs, setAuditLogs] = useState<RemediationAuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Approval / Rejection modal state
  const [selectedRec, setSelectedRec] = useState<RemediationRecommendation | null>(null);
  const [actionModalType, setActionModalType] = useState<"approve" | "reject" | null>(null);
  const [operatorId, setOperatorId] = useState("sre-lead@opspilot.io");
  const [operatorRole, setOperatorRole] = useState<UserRole>("SRE_LEAD");
  const [commentOrReason, setCommentOrReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actionResult, setActionResult] = useState<string | null>(null);

  // Direct simulation state
  const [directActionType, setDirectActionType] = useState<RemediationActionType>("restart_service");
  const [directService, setDirectService] = useState(serviceId || "api-gateway");
  const [directSimulating, setDirectSimulating] = useState(false);

  // Active view tab: recommendations vs audit logs
  const [activeTab, setActiveTab] = useState<"recommendations" | "audit_trail" | "simulator">("recommendations");

  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [recs, logs] = await Promise.all([
          fetchRemediationRecommendations(incidentId),
          fetchRemediationAuditLogs(incidentId),
        ]);
        if (isMounted) {
          setRecommendations(recs);
          setAuditLogs(logs);
        }
      } catch (err: unknown) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load remediation data");
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadData();
    return () => {
      isMounted = false;
    };
  }, [incidentId]);

  const refreshData = async () => {
    try {
      const [recs, logs] = await Promise.all([
        fetchRemediationRecommendations(incidentId),
        fetchRemediationAuditLogs(incidentId),
      ]);
      setRecommendations(recs);
      setAuditLogs(logs);
      if (onIncidentUpdated) onIncidentUpdated();
    } catch {
      // silent refresh fallback
    }
  };

  const handleApprove = async () => {
    if (!selectedRec) return;
    setSubmitting(true);
    setActionResult(null);
    try {
      const updated = await approveRemediation(selectedRec.id, {
        approved_by: operatorId,
        user_role: operatorRole,
        comment: commentOrReason || "Approved via OpsPilot SRE Human-In-The-Loop Console",
      });
      setActionResult(`Action '${updated.action_type}' approved and successfully simulated in safe sandbox!`);
      setTimeout(() => {
        setActionModalType(null);
        setSelectedRec(null);
        setCommentOrReason("");
        setActionResult(null);
        refreshData();
      }, 1500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Approval failed");
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!selectedRec) return;
    if (!commentOrReason.trim()) {
      alert("Please provide a mandatory rejection rationale for the security audit log.");
      return;
    }
    setSubmitting(true);
    setActionResult(null);
    try {
      await rejectRemediation(selectedRec.id, {
        rejected_by: operatorId,
        user_role: operatorRole,
        rejection_reason: commentOrReason,
      });
      setActionResult(`Recommendation '${selectedRec.id}' rejected and recorded in immutable audit log.`);
      setTimeout(() => {
        setActionModalType(null);
        setSelectedRec(null);
        setCommentOrReason("");
        setActionResult(null);
        refreshData();
      }, 1500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Rejection failed");
      setSubmitting(false);
    }
  };

  const handleDirectSimulate = async () => {
    setDirectSimulating(true);
    setError(null);
    try {
      const defaultParams: Record<RemediationActionType, Record<string, unknown>> = {
        restart_service: { grace_period_seconds: 30, rolling: true },
        scale_service: { replicas: 4, direction: "up" },
        rollback_deployment: { target_revision: "1", verify_canary: true },
        clear_cache: { cache_cluster: "redis-cluster", key_pattern: "session:*" },
        toggle_circuit_breaker: { dependency_service: "payment-gateway", target_state: "OPEN" },
      };

      const result = await simulateRemediationAction({
        action_type: directActionType,
        target_service: directService,
        parameters: defaultParams[directActionType],
        operator_id: operatorId,
        user_role: operatorRole,
      });

      alert(`Simulation completed: ${result.executor_result.output}`);
      await refreshData();
      setActiveTab("audit_trail");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Direct simulation failed");
    } finally {
      setDirectSimulating(false);
    }
  };

  const getStatusBadge = (status: RemediationStatus) => {
    switch (status) {
      case "RECOMMENDED":
        return (
          <span
            className="chip"
            style={{
              background: "rgba(201, 162, 39, 0.2)",
              color: "var(--signal-wait)",
              fontWeight: 700,
              border: "1px solid rgba(201, 162, 39, 0.4)",
              letterSpacing: "0.05em",
            }}
          >
            ● RECOMMENDED
          </span>
        );
      case "APPROVED":
        return (
          <span
            className="chip"
            style={{
              background: "rgba(78, 140, 255, 0.2)",
              color: "#4E8CFF",
              fontWeight: 700,
              border: "1px solid rgba(78, 140, 255, 0.4)",
              letterSpacing: "0.05em",
            }}
          >
            ✓ APPROVED
          </span>
        );
      case "EXECUTING":
        return (
          <span
            className="chip"
            style={{
              background: "rgba(0, 210, 255, 0.2)",
              color: "#00D2FF",
              fontWeight: 700,
              border: "1px solid rgba(0, 210, 255, 0.4)",
              letterSpacing: "0.05em",
              animation: "pulse 1.5s infinite",
            }}
          >
            ⏳ EXECUTING
          </span>
        );
      case "SUCCESS":
        return (
          <span
            className="chip"
            style={{
              background: "rgba(143, 191, 159, 0.25)",
              color: "var(--sage)",
              fontWeight: 700,
              border: "1px solid rgba(143, 191, 159, 0.4)",
              letterSpacing: "0.05em",
            }}
          >
            ✓ SUCCESS
          </span>
        );
      case "FAILED":
        return (
          <span
            className="chip"
            style={{
              background: "rgba(211, 106, 88, 0.25)",
              color: "var(--signal-bad)",
              fontWeight: 700,
              border: "1px solid rgba(211, 106, 88, 0.4)",
              letterSpacing: "0.05em",
            }}
          >
            ✕ FAILED
          </span>
        );
      case "REJECTED":
        return (
          <span
            className="chip"
            style={{
              background: "rgba(100, 100, 100, 0.2)",
              color: "var(--ink-faint)",
              fontWeight: 700,
              border: "1px solid rgba(100, 100, 100, 0.4)",
              letterSpacing: "0.05em",
            }}
          >
            ⊘ REJECTED
          </span>
        );
      default:
        return <Badge variant="neutral">{status}</Badge>;
    }
  };

  return (
    <div style={{ display: "grid", gap: 20 }}>
      {/* 1. Security & Safety Guarantee Banner */}
      <div
        style={{
          padding: "16px 20px",
          borderRadius: 12,
          background: "linear-gradient(135deg, rgba(20, 26, 31, 0.95) 0%, rgba(30, 39, 46, 0.95) 100%)",
          border: "1px solid rgba(143, 191, 159, 0.3)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: "50%",
              background: "rgba(143, 191, 159, 0.15)",
              border: "1px solid var(--sage)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 18,
              color: "var(--sage)",
            }}
          >
            🛡️
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <strong style={{ color: "var(--ink)", fontSize: 15 }}>
                Human-In-The-Loop Safety Boundary Active
              </strong>
              <span
                className="chip"
                style={{
                  background: "rgba(143, 191, 159, 0.2)",
                  color: "var(--sage)",
                  fontSize: 11,
                  fontWeight: 600,
                }}
              >
                Safe Simulation Sandbox
              </span>
            </div>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--ink-dim)", lineHeight: 1.4 }}>
              Zero arbitrary bash shell commands, zero unrestricted AWS CLI mutations, zero raw SQL execution.
              All actions require explicit human operator authorization and execute strictly through strongly typed allowlists.
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 12, color: "var(--ink-faint)" }}>
            Operator Role:
          </span>
          <select
            value={operatorRole}
            onChange={(e) => setOperatorRole(e.target.value as UserRole)}
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              background: "var(--bg-sub)",
              color: "var(--ink)",
              border: "1px solid var(--line)",
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            <option value="SRE_LEAD">SRE_LEAD (Full Authorization)</option>
            <option value="OPERATOR">OPERATOR (LOW Risk Only)</option>
            <option value="PLATFORM_ADMIN">PLATFORM_ADMIN (Superuser)</option>
            <option value="VIEWER">VIEWER (Read-Only)</option>
          </select>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: 8,
            background: "rgba(211, 106, 88, 0.15)",
            border: "1px solid var(--signal-bad)",
            color: "var(--signal-bad)",
            fontSize: 13,
          }}
        >
          <strong>Security Notice: </strong> {error}
        </div>
      )}

      {/* 2. Tab Navigation */}
      <div style={{ display: "flex", gap: 10, borderBottom: "1px solid var(--line)", paddingBottom: 10 }}>
        <button
          className={`filter-btn ${activeTab === "recommendations" ? "active" : ""}`}
          onClick={() => setActiveTab("recommendations")}
        >
          Allowlisted Recommendations ({recommendations.length})
        </button>
        <button
          className={`filter-btn ${activeTab === "audit_trail" ? "active" : ""}`}
          onClick={() => setActiveTab("audit_trail")}
        >
          Security Audit Trail ({auditLogs.length})
        </button>
        <button
          className={`filter-btn ${activeTab === "simulator" ? "active" : ""}`}
          onClick={() => setActiveTab("simulator")}
        >
          Sandbox Action Tester
        </button>
      </div>

      {/* 3. Tab 1: Recommendations List */}
      {activeTab === "recommendations" && (
        <div style={{ display: "grid", gap: 16 }}>
          {loading ? (
            <LoadingSpinner message="Querying allowlisted remediation catalog..." />
          ) : recommendations.length === 0 ? (
            <EmptyState message="No pending remediation recommendations found for this incident." />
          ) : (
            recommendations.map((rec) => (
              <Card
                key={rec.id}
                kicker={`ALLOWLISTED ACTION · ${rec.action_type.toUpperCase()}`}
                title={rec.rationale}
                actions={
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        fontSize: 11,
                        padding: "3px 8px",
                        borderRadius: 4,
                        background:
                          rec.risk_level === "HIGH"
                            ? "rgba(211, 106, 88, 0.15)"
                            : rec.risk_level === "MEDIUM"
                            ? "rgba(201, 162, 39, 0.15)"
                            : "rgba(143, 191, 159, 0.15)",
                        color:
                          rec.risk_level === "HIGH"
                            ? "var(--signal-bad)"
                            : rec.risk_level === "MEDIUM"
                            ? "var(--signal-wait)"
                            : "var(--sage)",
                        fontWeight: 700,
                      }}
                    >
                      {rec.risk_level} RISK
                    </span>
                    {getStatusBadge(rec.status)}
                  </div>
                }
              >
                <div style={{ display: "grid", gap: 12, marginTop: 4 }}>
                  {/* Parameter Grid */}
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 8,
                      alignItems: "center",
                      fontSize: 12,
                    }}
                  >
                    <span style={{ color: "var(--ink-faint)" }}>Target Service:</span>
                    <strong style={{ color: "var(--ink)", fontFamily: "var(--mono)" }}>
                      {rec.target_service}
                    </strong>
                    <span style={{ color: "var(--line)" }}>|</span>
                    <span style={{ color: "var(--ink-faint)" }}>Parameters:</span>
                    <code
                      style={{
                        padding: "2px 8px",
                        borderRadius: 4,
                        background: "rgba(0, 0, 0, 0.3)",
                        fontFamily: "var(--mono)",
                        color: "var(--ink)",
                      }}
                    >
                      {JSON.stringify(rec.parameters)}
                    </code>
                    {rec.runbook_reference && (
                      <>
                        <span style={{ color: "var(--line)" }}>|</span>
                        <span style={{ color: "var(--ink-faint)" }}>Runbook:</span>
                        <span style={{ color: "var(--sage)" }}>{rec.runbook_reference}</span>
                      </>
                    )}
                  </div>

                  {/* Command Preview Box */}
                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: 8,
                      background: "rgba(0, 0, 0, 0.45)",
                      border: "1px solid var(--line)",
                      fontFamily: "var(--mono)",
                      fontSize: 13,
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      color: "var(--ink)",
                    }}
                  >
                    <div>
                      <span style={{ color: "var(--ink-faint)", userSelect: "none" }}>$ </span>
                      <span>{rec.command_preview}</span>
                    </div>
                    <span
                      style={{
                        fontSize: 11,
                        color: "var(--filament)",
                        background: "rgba(212, 120, 74, 0.15)",
                        padding: "2px 6px",
                        borderRadius: 4,
                      }}
                    >
                      Simulation Mode
                    </span>
                  </div>

                  {/* Operator Actions based on Status */}
                  {rec.status === "RECOMMENDED" && (
                    <div style={{ display: "flex", gap: 10, marginTop: 6 }}>
                      <button
                        className="filter-btn"
                        style={{
                          background: "linear-gradient(135deg, rgba(78, 140, 255, 0.25) 0%, rgba(50, 100, 230, 0.35) 100%)",
                          color: "#70A6FF",
                          borderColor: "rgba(78, 140, 255, 0.5)",
                          fontWeight: 700,
                          padding: "8px 16px",
                        }}
                        onClick={() => {
                          setSelectedRec(rec);
                          setActionModalType("approve");
                        }}
                      >
                        ✓ Human Approval & Execute Simulation
                      </button>

                      <button
                        className="filter-btn"
                        style={{
                          background: "rgba(211, 106, 88, 0.15)",
                          color: "var(--signal-bad)",
                          borderColor: "rgba(211, 106, 88, 0.4)",
                          fontWeight: 600,
                          padding: "8px 16px",
                        }}
                        onClick={() => {
                          setSelectedRec(rec);
                          setActionModalType("reject");
                        }}
                      >
                        ⊘ Reject Recommendation
                      </button>
                    </div>
                  )}

                  {rec.status === "SUCCESS" && (
                    <div
                      style={{
                        padding: "8px 12px",
                        borderRadius: 6,
                        background: "rgba(143, 191, 159, 0.1)",
                        border: "1px solid rgba(143, 191, 159, 0.3)",
                        fontSize: 12,
                        color: "var(--sage)",
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <span>✓ Remediation validated successfully in simulation sandbox. Parent incident updated to MITIGATED.</span>
                    </div>
                  )}

                  {rec.status === "REJECTED" && (
                    <div
                      style={{
                        padding: "8px 12px",
                        borderRadius: 6,
                        background: "rgba(100, 100, 100, 0.15)",
                        border: "1px solid rgba(100, 100, 100, 0.3)",
                        fontSize: 12,
                        color: "var(--ink-faint)",
                      }}
                    >
                      <span>⊘ Action declined by operator. Rationale permanently committed to immutable audit log.</span>
                    </div>
                  )}
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* 4. Tab 2: Security Audit Trail */}
      {activeTab === "audit_trail" && (
        <div style={{ display: "grid", gap: 14 }}>
          {auditLogs.length === 0 ? (
            <EmptyState message="No audit log entries recorded yet. Operator approvals and rejections will appear here." />
          ) : (
            auditLogs.map((log) => (
              <div
                key={log.id}
                style={{
                  padding: "16px 20px",
                  borderRadius: 10,
                  background: "var(--bg-panel)",
                  border: "1px solid var(--line)",
                  display: "grid",
                  gap: 10,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span
                      style={{
                        fontSize: 11,
                        padding: "2px 8px",
                        borderRadius: 4,
                        background: "rgba(212, 120, 74, 0.15)",
                        color: "var(--filament)",
                        fontFamily: "var(--mono)",
                        fontWeight: 600,
                      }}
                    >
                      {log.id}
                    </span>
                    <strong style={{ fontSize: 14, color: "var(--ink)" }}>
                      {log.requested_action}
                    </strong>
                    <span style={{ fontSize: 12, color: "var(--ink-dim)" }}>
                      on incident <code>{log.incident_id}</code>
                    </span>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 11, color: "var(--ink-faint)" }}>
                      {new Date(log.timestamp).toLocaleString()}
                    </span>
                    {getStatusBadge(log.status as RemediationStatus)}
                  </div>
                </div>

                {/* Approver / Rejector Info */}
                <div style={{ fontSize: 13, display: "flex", gap: 16, flexWrap: "wrap" }}>
                  <div>
                    <span style={{ color: "var(--ink-faint)" }}>Operator: </span>
                    <strong style={{ color: "var(--ink)" }}>
                      {log.user_approval.approved_by || log.user_approval.rejected_by || "System"}
                    </strong>{" "}
                    <span style={{ color: "var(--filament)", fontSize: 11 }}>
                      ({log.user_approval.user_role})
                    </span>
                  </div>

                  {log.user_approval.comment && (
                    <div>
                      <span style={{ color: "var(--ink-faint)" }}>Comment / Justification: </span>
                      <span style={{ color: "var(--ink)" }}>{log.user_approval.comment}</span>
                    </div>
                  )}

                  {log.executor_result.execution_duration_ms > 0 && (
                    <div>
                      <span style={{ color: "var(--ink-faint)" }}>Latency: </span>
                      <span style={{ color: "var(--sage)", fontFamily: "var(--mono)" }}>
                        {log.executor_result.execution_duration_ms.toFixed(1)}ms
                      </span>
                    </div>
                  )}

                  {log.executor_result.rollback_point && (
                    <div>
                      <span style={{ color: "var(--ink-faint)" }}>Rollback Point: </span>
                      <code style={{ color: "var(--filament)", fontSize: 11 }}>
                        {log.executor_result.rollback_point}
                      </code>
                    </div>
                  )}
                </div>

                {/* Execution Logs Terminal */}
                {log.executor_result.logs && log.executor_result.logs.length > 0 && (
                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: 8,
                      background: "rgba(0, 0, 0, 0.4)",
                      border: "1px solid var(--line)",
                      fontFamily: "var(--mono)",
                      fontSize: 12,
                      display: "grid",
                      gap: 4,
                    }}
                  >
                    {log.executor_result.logs.map((line, idx) => (
                      <div key={idx} style={{ color: "var(--ink-dim)" }}>
                        {line}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* 5. Tab 3: Direct Action Sandbox Tester */}
      {activeTab === "simulator" && (
        <Card
          kicker="OPERATOR SANDBOX"
          title="Direct Allowlisted Action Simulator"
        >
          <div style={{ display: "grid", gap: 16 }}>
            <p style={{ margin: 0, fontSize: 13, color: "var(--ink-dim)" }}>
              Directly invoke an allowlisted remediation action in Safe Simulation Mode to test cluster latency, health verification, and rollback point checkpointing.
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={{ display: "block", fontSize: 12, color: "var(--ink-faint)", marginBottom: 6 }}>
                  Select Allowlisted Action:
                </label>
                <select
                  value={directActionType}
                  onChange={(e) => setDirectActionType(e.target.value as RemediationActionType)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: "var(--bg-sub)",
                    color: "var(--ink)",
                    border: "1px solid var(--line)",
                    fontSize: 13,
                  }}
                >
                  <option value="restart_service">restart_service (Rolling pod restart)</option>
                  <option value="scale_service">scale_service (Replica adjustment 1..20)</option>
                  <option value="rollback_deployment">rollback_deployment (Deterministic undo)</option>
                  <option value="clear_cache">clear_cache (Pattern-based Redis eviction)</option>
                  <option value="toggle_circuit_breaker">toggle_circuit_breaker (Istio mesh trip)</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, color: "var(--ink-faint)", marginBottom: 6 }}>
                  Target Service Slug:
                </label>
                <input
                  type="text"
                  value={directService}
                  onChange={(e) => setDirectService(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: "var(--bg-sub)",
                    color: "var(--ink)",
                    border: "1px solid var(--line)",
                    fontSize: 13,
                    fontFamily: "var(--mono)",
                  }}
                />
              </div>
            </div>

            <div style={{ display: "flex", gap: 12 }}>
              <button
                className="filter-btn"
                style={{
                  background: "var(--sage)",
                  color: "#0B1115",
                  fontWeight: 700,
                  padding: "10px 20px",
                }}
                disabled={directSimulating}
                onClick={handleDirectSimulate}
              >
                {directSimulating ? "Executing Simulation..." : "▶ Run Sandbox Simulation"}
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* 6. Approval / Rejection Modal */}
      {actionModalType && selectedRec && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(6px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              width: "100%",
              maxWidth: 540,
              background: "var(--bg-panel)",
              borderRadius: 14,
              border: "1px solid var(--line)",
              padding: 24,
              display: "grid",
              gap: 16,
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong style={{ fontSize: 16, color: "var(--ink)" }}>
                {actionModalType === "approve"
                  ? "Authorize Remediation Execution"
                  : "Reject Remediation Recommendation"}
              </strong>
              <button
                style={{ background: "none", border: "none", color: "var(--ink-faint)", fontSize: 18, cursor: "pointer" }}
                onClick={() => setActionModalType(null)}
              >
                ✕
              </button>
            </div>

            <div style={{ fontSize: 13, color: "var(--ink-dim)", lineHeight: 1.4 }}>
              {actionModalType === "approve" ? (
                <>
                  You are approving allowlisted action{" "}
                  <strong style={{ color: "var(--ink)" }}>{selectedRec.action_type}</strong> for{" "}
                  <strong style={{ color: "var(--ink)" }}>{selectedRec.target_service}</strong>.
                  Execution will run in <strong style={{ color: "var(--sage)" }}>Safe Simulation Mode</strong> and be recorded in the immutable audit log.
                </>
              ) : (
                <>
                  You are rejecting allowlisted action{" "}
                  <strong style={{ color: "var(--ink)" }}>{selectedRec.action_type}</strong>.
                  A mandatory rationale must be provided for post-incident review and compliance records.
                </>
              )}
            </div>

            <div style={{ display: "grid", gap: 10 }}>
              <div>
                <label style={{ display: "block", fontSize: 12, color: "var(--ink-faint)", marginBottom: 4 }}>
                  Approving Operator:
                </label>
                <input
                  type="text"
                  value={operatorId}
                  onChange={(e) => setOperatorId(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: "var(--bg-sub)",
                    color: "var(--ink)",
                    border: "1px solid var(--line)",
                    fontSize: 13,
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, color: "var(--ink-faint)", marginBottom: 4 }}>
                  {actionModalType === "approve" ? "Optional Operator Note:" : "Mandatory Rejection Rationale:"}
                </label>
                <textarea
                  rows={3}
                  value={commentOrReason}
                  onChange={(e) => setCommentOrReason(e.target.value)}
                  placeholder={
                    actionModalType === "approve"
                      ? "e.g. Verified database connection pool limits. Scaling approved."
                      : "e.g. Root cause identified as network partition; rolling restart would cause cluster quorum loss."
                  }
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: "var(--bg-sub)",
                    color: "var(--ink)",
                    border: "1px solid var(--line)",
                    fontSize: 13,
                    fontFamily: "inherit",
                    resize: "vertical",
                  }}
                />
              </div>
            </div>

            {actionResult && (
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: 6,
                  background: "rgba(143, 191, 159, 0.2)",
                  color: "var(--sage)",
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                {actionResult}
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 4 }}>
              <button
                className="filter-btn"
                onClick={() => setActionModalType(null)}
                disabled={submitting}
              >
                Cancel
              </button>
              {actionModalType === "approve" ? (
                <button
                  className="filter-btn"
                  style={{
                    background: "#4E8CFF",
                    color: "#FFFFFF",
                    fontWeight: 700,
                    borderColor: "#4E8CFF",
                  }}
                  disabled={submitting}
                  onClick={handleApprove}
                >
                  {submitting ? "Executing..." : "Confirm & Execute Simulation"}
                </button>
              ) : (
                <button
                  className="filter-btn"
                  style={{
                    background: "var(--signal-bad)",
                    color: "#FFFFFF",
                    fontWeight: 700,
                    borderColor: "var(--signal-bad)",
                  }}
                  disabled={submitting}
                  onClick={handleReject}
                >
                  {submitting ? "Rejecting..." : "Confirm Rejection"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
