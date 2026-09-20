import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { useEffect, useState } from "react";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="shell">
      <Sidebar />
      <main className="main">
        <header className="topbar">
          <div>
            <p className="kicker">Night desk · local</p>
            <h1>Instrument check</h1>
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
