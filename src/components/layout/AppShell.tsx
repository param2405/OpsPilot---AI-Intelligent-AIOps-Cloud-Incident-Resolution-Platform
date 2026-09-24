import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";

type AppShellProps = {
  children: ReactNode;
};

const routeHeaders: Record<string, { kicker: string; title: string }> = {
  "/": { kicker: "Phase 2 · Telemetry Fleet", title: "Operations fleet overview" },
  "/dashboard": { kicker: "Phase 2 · Telemetry Fleet", title: "Operations fleet overview" },
  "/incidents": { kicker: "Phase 2 · Incident Command", title: "Incident registry" },
  "/metrics": { kicker: "Phase 2 · Observability", title: "Telemetry streams & anomaly overlay" },
  "/logs": { kicker: "Phase 2 · Ingestion", title: "Distributed log explorer" },
  "/foundation": { kicker: "Phase 1 · Foundation", title: "Instrument check" },
  "/ml": { kicker: "Phase 3 · Machine Learning", title: "ML engine & model registry" },
  "/deep-learning": { kicker: "Phase 4 · Deep Learning", title: "Log sequence attention & embeddings" },
  "/rag": { kicker: "Phase 5 · Production RAG", title: "Grounded Q&A & runbook knowledge" },
  "/investigation": { kicker: "Phase 6 · LangGraph Agent", title: "AI incident investigation" },
  "/recommendations": { kicker: "Phase 6 · LangGraph Agent", title: "AI incident investigation" },
  "/settings": { kicker: "System Config", title: "Platform settings" },
};


export function AppShell({ children }: AppShellProps) {
  const [now, setNow] = useState(() => new Date());
  const location = useLocation();

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const headerInfo = routeHeaders[location.pathname] ?? {
    kicker: "Night desk · OpsPilot",
    title: "Operations Console",
  };

  return (
    <div className="shell">
      <Sidebar />
      <main className="main">
        <header className="topbar">
          <div>
            <p className="kicker">{headerInfo.kicker}</p>
            <h1>{headerInfo.title}</h1>
          </div>
          <div className="clock">
            <time dateTime={now.toISOString()}>
              {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </time>
            <span>{now.toLocaleDateString(undefined, { weekday: "short", day: "2-digit", month: "short" })}</span>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
