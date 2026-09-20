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
          version: "0.1.0",
          database: { connected: true, detail: "PostgreSQL accepted SELECT 1." },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    return new Response(
      JSON.stringify({
        status: "ok",
        service: "OpsPilot AI",
        environment: "test",
        version: "0.1.0",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }),
);

describe("foundation console", () => {
  it("renders the Phase 1 shell and honest scope copy", async () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Instrument check" })).toBeInTheDocument();
    expect(screen.getByText(/Anomaly detection, classification, RAG, and agents/i)).toBeInTheDocument();
    expect(await screen.findByText(/ok · 0\.1\.0/i)).toBeInTheDocument();
  });
});
