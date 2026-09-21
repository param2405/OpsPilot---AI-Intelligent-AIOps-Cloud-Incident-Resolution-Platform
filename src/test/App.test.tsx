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

describe("OpsPilot Phase 2 Surfaces", () => {
  it("renders the Phase 2 Dashboard at root path", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Operations fleet overview" })).toBeInTheDocument();
    expect(screen.getByText(/Phase 2 · Telemetry & Ingestion Live/i)).toBeInTheDocument();
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
    expect(screen.getByText(/P1 CRITICAL/i)).toBeInTheDocument();
  });
});
