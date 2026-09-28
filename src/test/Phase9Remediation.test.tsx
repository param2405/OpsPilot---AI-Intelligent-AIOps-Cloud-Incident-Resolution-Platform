import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi, describe, it, expect, beforeEach } from "vitest";
import App from "../App";
import { RemediationControlCenter } from "../components/RemediationControlCenter";

const mockRecommendations = [
  {
    id: "REC-2026-001",
    incident_id: "INC-2026-001",
    action_type: "scale_service",
    target_service: "api-gateway",
    parameters: { service_name: "api-gateway", replicas: 5, direction: "up" },
    rationale: "Scale API gateway pods to handle surge in ingress traffic.",
    risk_level: "LOW",
    status: "RECOMMENDED",
    command_preview: "kubectl scale deployment/api-gateway --replicas=5",
    runbook_reference: "Runbook: SRE-SCALE-UP",
    created_at: "2026-09-28T09:00:00Z",
    updated_at: "2026-09-28T09:00:00Z",
  },
  {
    id: "REC-2026-002",
    incident_id: "INC-2026-001",
    action_type: "restart_service",
    target_service: "auth-service",
    parameters: { service_name: "auth-service", grace_period_seconds: 30 },
    rationale: "Rolling restart of auth service to flush memory leak.",
    risk_level: "LOW",
    status: "SUCCESS",
    command_preview: "kubectl rollout restart deployment/auth-service",
    runbook_reference: "Runbook: SRE-ROLLOUT-RESTART",
    created_at: "2026-09-28T08:00:00Z",
    updated_at: "2026-09-28T08:05:00Z",
  },
  {
    id: "REC-2026-003",
    incident_id: "INC-2026-001",
    action_type: "rollback_deployment",
    target_service: "order-service",
    parameters: { service_name: "order-service", target_revision: "1" },
    rationale: "Rollback deployment v2.4.0 due to missing environment key.",
    risk_level: "HIGH",
    status: "REJECTED",
    command_preview: "kubectl rollout undo deployment/order-service --to-revision=1",
    runbook_reference: "Runbook: SRE-ROLLBACK",
    created_at: "2026-09-28T07:00:00Z",
    updated_at: "2026-09-28T07:10:00Z",
  },
];

const mockAuditLogs = [
  {
    id: "AUD-2026-001",
    recommendation_id: "REC-2026-002",
    incident_id: "INC-2026-001",
    requested_action: "restart_service",
    action_parameters: { service_name: "auth-service", grace_period_seconds: 30 },
    simulation_mode: true,
    user_approval: {
      approved_by: "sre-lead@opspilot.io",
      user_role: "SRE_LEAD",
      comment: "Approved after verifying traffic routing",
      approval_status: "APPROVED",
    },
    executor_result: {
      output: "Restart simulation succeeded.",
      execution_duration_ms: 45.2,
      simulated: true,
      validation_passed: true,
      logs: ["[SIMULATOR] Restarted deployment/auth-service pods safely."],
      rollback_point: "deployment/auth-service:rev-4",
    },
    status: "SUCCESS",
    timestamp: "2026-09-28T08:05:00Z",
  },
];

describe("Phase 9: Human-In-The-Loop Remediation Workflow", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo) => {
        const url = String(input);

        if (url.includes("/remediations/recommendations") && !url.includes("/approve") && !url.includes("/reject")) {
          return new Response(JSON.stringify(mockRecommendations), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url.includes("/remediations/audit-logs")) {
          return new Response(JSON.stringify(mockAuditLogs), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url.includes("/approve")) {
          const approved = { ...mockRecommendations[0], status: "SUCCESS" };
          return new Response(JSON.stringify(approved), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url.includes("/reject")) {
          const rejected = { ...mockRecommendations[0], status: "REJECTED" };
          return new Response(JSON.stringify(rejected), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        // Default mock response
        return new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
  });

  it("renders the Safety Boundary active banner with explicit allowlist guarantee", async () => {
    render(<RemediationControlCenter incidentId="INC-2026-001" />);

    expect(
      await screen.findByText(/Human-In-The-Loop Safety Boundary Active/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Zero arbitrary bash shell commands, zero unrestricted AWS CLI mutations/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Safe Simulation Sandbox/i)).toBeInTheDocument();
  });

  it("renders allowlisted recommendations clearly distinguishing status badges", async () => {
    render(<RemediationControlCenter incidentId="INC-2026-001" />);

    // Recommended badge
    expect(await screen.findByText(/● RECOMMENDED/i)).toBeInTheDocument();
    // Success badge
    expect(screen.getByText(/✓ SUCCESS/i)).toBeInTheDocument();
    // Rejected badge
    expect(screen.getByText(/⊘ REJECTED/i)).toBeInTheDocument();

    // Verify allowlisted actions displayed
    expect(screen.getByText(/ALLOWLISTED ACTION · SCALE_SERVICE/i)).toBeInTheDocument();
    expect(screen.getByText(/ALLOWLISTED ACTION · RESTART_SERVICE/i)).toBeInTheDocument();
    expect(screen.getByText(/ALLOWLISTED ACTION · ROLLBACK_DEPLOYMENT/i)).toBeInTheDocument();
  });

  it("opens human approval modal and executes simulation upon operator confirmation", async () => {
    render(<RemediationControlCenter incidentId="INC-2026-001" />);

    const approveBtn = await screen.findByText(/✓ Human Approval & Execute Simulation/i);
    expect(approveBtn).toBeInTheDocument();

    fireEvent.click(approveBtn);

    // Modal opens
    expect(screen.getByText(/Authorize Remediation Execution/i)).toBeInTheDocument();
    expect(screen.getByText(/Confirm & Execute Simulation/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/Confirm & Execute Simulation/i));

    await waitFor(() => {
      expect(
        screen.getByText(/approved and successfully simulated in safe sandbox/i)
      ).toBeInTheDocument();
    });
  });

  it("switches to Security Audit Trail tab and displays immutable log entries", async () => {
    render(<RemediationControlCenter incidentId="INC-2026-001" />);

    const auditTabBtn = await screen.findByRole("button", { name: /Security Audit Trail/i });
    fireEvent.click(auditTabBtn);

    expect(await screen.findByText(/AUD-2026-001/i)).toBeInTheDocument();
    expect(screen.getByText(/sre-lead@opspilot.io/i)).toBeInTheDocument();
    expect(screen.getByText(/Approved after verifying traffic routing/i)).toBeInTheDocument();
    expect(screen.getByText(/Restarted deployment\/auth-service pods safely/i)).toBeInTheDocument();
  });

  it("navigates to /remediation route and renders the Remediation Console", async () => {
    render(
      <MemoryRouter initialEntries={["/remediation"]}>
        <App />
      </MemoryRouter>
    );

    expect(
      await screen.findByText(/Human-In-The-Loop Remediation Console/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Phase 9 · Safety Gateway/i)
    ).toBeInTheDocument();
  });
});
