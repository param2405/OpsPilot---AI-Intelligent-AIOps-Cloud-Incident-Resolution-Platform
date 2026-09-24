import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import App from "../App";

vi.stubGlobal(
  "fetch",
  vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (url.includes("/health/ready")) {
      return new Response(
        JSON.stringify({
          status: "ready",
          service: "OpsPilot AI",
          environment: "test",
          version: "0.2.0",
          database: { connected: true, detail: "PostgreSQL accepted SELECT 1." },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    if (url.includes("/health")) {
      return new Response(
        JSON.stringify({
          status: "ok",
          service: "OpsPilot AI",
          environment: "test",
          version: "0.2.0",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    return new Response(JSON.stringify([]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }),
);

describe("OpsPilot Platform Surfaces (Phases 1 - 6)", () => {
  it("renders the Dashboard at root path with Phase 6 status", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Operations fleet overview" })).toBeInTheDocument();
    expect(screen.getByText(/Phase 6 · Autonomous LangGraph Agent Live/i)).toBeInTheDocument();
    expect(screen.getByText(/Monitored Services/i)).toBeInTheDocument();
  });

  it("renders the Foundation instrument check at /foundation", async () => {
    render(
      <MemoryRouter initialEntries={["/foundation"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Instrument check" })).toBeInTheDocument();
    expect(screen.getByText(/Anomaly detection, classification, RAG, and agents/i)).toBeInTheDocument();
  });

  it("renders the Incident Registry at /incidents", async () => {
    render(
      <MemoryRouter initialEntries={["/incidents"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Incident registry" })).toBeInTheDocument();
  });

  it("renders the Phase 6 AI Investigation Agent at /investigation", async () => {
    render(
      <MemoryRouter initialEntries={["/investigation"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "AI incident investigation" })).toBeInTheDocument();
    expect(screen.getByText(/LangGraph Investigation Graph/i)).toBeInTheDocument();
  });

  it("renders the Phase 3 ML Engine at /ml", async () => {
    render(
      <MemoryRouter initialEntries={["/ml"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "ML engine & model registry" })).toBeInTheDocument();
    expect(screen.getAllByText(/Isolation Forest/i).length).toBeGreaterThan(0);
  });

  it("renders the Phase 4 Deep Learning at /deep-learning", async () => {
    render(
      <MemoryRouter initialEntries={["/deep-learning"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Log sequence attention & embeddings" })).toBeInTheDocument();
    expect(screen.getAllByText(/BiLSTM/i).length).toBeGreaterThan(0);
  });

  it("renders the Phase 5 RAG Knowledge at /rag", async () => {
    render(
      <MemoryRouter initialEntries={["/rag"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Grounded Q&A & runbook knowledge" })).toBeInTheDocument();
    expect(screen.getByText(/Grounded Knowledge Q&A/i)).toBeInTheDocument();
  });
});


