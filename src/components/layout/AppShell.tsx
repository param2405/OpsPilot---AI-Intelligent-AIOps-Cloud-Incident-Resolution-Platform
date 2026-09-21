import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";

type AppShellProps = {
  children: ReactNode;
};

const routeHeaders: Record<string, { kicker: string; title: string }> = {
  "/": { kicker: "Night desk · Telemetry", title: "Operations fleet overview" },
  "/dashboard": { kicker: "Night desk · Telemetry", title: "Operations fleet overview" },
  "/incidents": { kicker: "Incident command · Active", title: "Incident registry" },
  "/metrics": { kicker: "Telemetry streams · Realtime", title: "Service metrics" },
  "/logs": { kicker: "Trace correlation · Ingestion", title: "Distributed log explorer" },
  "/foundation": { kicker: "Night desk · Local", title: "Instrument check" },
  "/investigation": { kicker: "Phase 3 · Diagnostic", title: "AI investigation" },
  "/recommendations": { kicker: "Phase 4 · Mitigation", title: "Recommendations" },
  "/settings": { kicker: "Phase 5 · Admin", title: "Settings" },
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
