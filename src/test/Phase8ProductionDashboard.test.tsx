import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi, describe, it, expect } from "vitest";
import App from "../App";

// Mock fetch to simulate real backend responses across Phase 8 APIs
vi.stubGlobal(
  "fetch",
  vi.fn(async (input: RequestInfo) => {
    const url = String(input);

    if (url.includes("/health/ready")) {
      return new Response(
        JSON.stringify({
          status: "ready",
          service: "OpsPilot AI",
          environment: "production",
          version: "0.2.0",
          database: { connected: true, detail: "PostgreSQL accepted SELECT 1." },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/orchestration/pipeline/status")) {
      return new Response(
        JSON.stringify({
          status: "healthy",
          pipeline_version: "2.1.0-orch",
          components: {
            ml_anomaly_detector: { status: "ready", version: "v1.2.0" },
            ml_classifier: { status: "ready", version: "v1.1.4" },
            ml_severity_predictor: { status: "ready", version: "v1.0.8" },
            deep_learning_sequence_model: { status: "ready", version: "bilstm-attention-v1", device: "cpu" },
            langgraph_agent: { status: "ready", nodes_count: 9 },
            rag_vector_store: { status: "ready", documents_indexed: 42 },
          },
          timestamp: "2026-09-28T09:00:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/orchestration/investigations")) {
      return new Response(
        JSON.stringify([
          {
            investigation_id: "INV-2026-001",
            incident_id: "INC-2026-001",
            service_id: "auth-service",
            status: "COMPLETED",
            detected_anomaly: true,
            anomaly_score: 0.94,
            predicted_category: "CPU_SATURATION",
            predicted_severity: "P1_CRITICAL",
            suspected_root_cause: "Catastrophic backtracking in regex claims parsing under sustained concurrent traffic",
            confidence: 0.91,
            degraded_components: ["auth-service", "JWT Verifier"],
            created_at: "2026-09-28T08:30:00Z",
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/api/v1/services")) {
      return new Response(
        JSON.stringify([
          { id: "auth-service", name: "Authentication Service", tier: "critical", environment: "production", created_at: "2026-09-01T00:00:00Z" },
          { id: "payment-service", name: "Payment Processing Service", tier: "critical", environment: "production", created_at: "2026-09-01T00:00:00Z" },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/api/v1/incidents")) {
      return new Response(
        JSON.stringify([
          {
            id: "INC-2026-001",
            incident_id: "INC-2026-001",
            title: "Auth Service CPU Starvation in JWT Verification Loop",
            service_id: "auth-service",
            severity: "P1_CRITICAL",
            status: "INVESTIGATING",
            incident_type: "CPU_SATURATION",
            symptoms: ["Auth service CPU pegged at 99%", "p95 latency spiked from 35ms to 1850ms"],
            root_cause: "Catastrophic backtracking in regex claims parsing under sustained concurrent traffic",
            detected_at: "2026-09-28T08:30:00Z",
            mitigated_at: null,
            resolved_at: null,
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/api/v1/metrics/summary")) {
      return new Response(
        JSON.stringify({
          service_id: "auth-service",
          sample_count: 24,
          avg_cpu_usage: 55.4,
          max_cpu_usage: 98.2,
          avg_memory_usage: 64.1,
          max_memory_usage: 81.3,
          avg_latency_p95_ms: 120.5,
          max_latency_p95_ms: 1850.0,
          avg_error_rate: 0.008,
          max_error_rate: 0.12,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/api/v1/metrics")) {
      return new Response(
        JSON.stringify([
          {
            id: 1,
            service_id: "auth-service",
            cpu_usage: 74.2,
            memory_usage: 68.1,
            latency_p95_ms: 240.0,
            error_rate: 0.015,
            timestamp: "2026-09-28T08:35:00Z",
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/api/v1/logs")) {
      return new Response(
        JSON.stringify([
          {
            id: 101,
            service_id: "auth-service",
            log_level: "ERROR",
            message: "JWT signature parsing thread timeout after 5000ms",
            trace_id: "tr-998811",
            timestamp: "2026-09-28T08:32:00Z",
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    return new Response(JSON.stringify([]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }),
);

describe("Phase 8 — Production React Dashboard Surfaces", () => {
  it("renders Page 1: Dashboard with telemetry KPIs, active incidents, and distribution", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Operations fleet overview" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Active Incidents/i)).toBeInTheDocument();
      expect(screen.getByText(/Monitored Services/i)).toBeInTheDocument();
      expect(screen.getByText(/Incident Severity Distribution/i)).toBeInTheDocument();
    });
  });

  it("renders Page 2: Incidents registry with filtering and search", async () => {
    render(
      <MemoryRouter initialEntries={["/incidents"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Incident registry", level: 1 })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Filter incidents by title, ID, symptom, or keyword/i)).toBeInTheDocument();
    expect(screen.getByText("P1 CRITICAL")).toBeInTheDocument();
  });

  it("renders Page 3: Incident Details with ML anomaly score, classification, RAG sources, and remediation", async () => {
    render(
      <MemoryRouter initialEntries={["/incidents/INC-2026-001"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Auth Service CPU Starvation in JWT Verification Loop/i)).toBeInTheDocument();
      expect(screen.getByText(/Anomaly Detection/i)).toBeInTheDocument();
      expect(screen.getByText(/Failure Domain Classifier/i)).toBeInTheDocument();
      expect(screen.getByText(/Severity Prediction/i)).toBeInTheDocument();
      expect(screen.getByText(/Recommended Remediation Runbook/i)).toBeInTheDocument();
      expect(screen.getByText(/Suspected Root Cause/i)).toBeInTheDocument();
    });
  });

  it("renders Page 4: Metrics telemetry explorer", async () => {
    render(
      <MemoryRouter initialEntries={["/metrics"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: /Telemetry streams & anomaly overlay/i })).toBeInTheDocument();
    expect(screen.getByText(/CPU Utilization/i)).toBeInTheDocument();
  });

  it("renders Page 5: Distributed Logs console", async () => {
    render(
      <MemoryRouter initialEntries={["/logs"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByText(/DISTRIBUTED STREAM CONSOLE/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Filter by keyword, exception, or token/i)).toBeInTheDocument();
  });

  it("renders Page 6: AI Investigation without exposing chain-of-thought", async () => {
    render(
      <MemoryRouter initialEntries={["/investigation"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "AI incident investigation" })).toBeInTheDocument();
    expect(screen.getByText(/StateGraph Multi-Node Workflow/i)).toBeInTheDocument();
    expect(screen.getByText(/Suspected Root Cause/i)).toBeInTheDocument();
  });

  it("renders Page 7: Historical Incidents archive with semantic search", async () => {
    render(
      <MemoryRouter initialEntries={["/historical-incidents"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Historical Incident Repository" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Semantic search/i)).toBeInTheDocument();
  });

  it("renders Page 8: Model Performance and benchmarks", async () => {
    render(
      <MemoryRouter initialEntries={["/model-performance"]}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Model Performance & Registry Benchmarks" })).toBeInTheDocument();
      expect(screen.getByText(/Isolation Forest Detector/i)).toBeInTheDocument();
      expect(screen.getByText(/BiLSTM \+ Multi-Head Attention/i)).toBeInTheDocument();
    });
  });

  it("renders Page 9: System Health and subsystem readiness", async () => {
    render(
      <MemoryRouter initialEntries={["/system-health"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Platform System Health" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/FastAPI & PostgreSQL Storage/i)).toBeInTheDocument();
      expect(screen.getByText(/Deterministic ML Pipelines/i)).toBeInTheDocument();
      expect(screen.getByText(/BiLSTM Attention Sequence Model/i)).toBeInTheDocument();
    });
  });
});
