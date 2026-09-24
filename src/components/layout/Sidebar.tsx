import { NavLink } from "react-router-dom";
import { Mark } from "../brand/Mark";

const items = [
  { to: "/foundation", label: "Foundation", idx: "01", phase: "P1", later: false },
  { to: "/", label: "Dashboard", idx: "02", phase: "P2", later: false },
  { to: "/incidents", label: "Incidents", idx: "03", phase: "P2", later: false },
  { to: "/metrics", label: "Metrics", idx: "04", phase: "P2", later: false },
  { to: "/logs", label: "Logs", idx: "05", phase: "P2", later: false },
  { to: "/ml", label: "ML Engine", idx: "06", phase: "P3", later: false },
  { to: "/deep-learning", label: "Deep Learning", idx: "07", phase: "P4", later: false },
  { to: "/rag", label: "RAG Knowledge", idx: "08", phase: "P5", later: false },
  { to: "/investigation", label: "AI Investigation", idx: "09", phase: "P6", later: false },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <Mark />
        <div className="brand-copy">
          <strong>OpsPilot AI</strong>
          <span>OP-06 / FULL AIOPS PLATFORM</span>
        </div>
      </div>
      <p className="nav-label">Platform Phases</p>
      <nav className="nav" aria-label="Primary">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/" || item.to === "/foundation"}
            className={({ isActive }) =>
              [isActive ? "active" : "", item.later ? "locked" : ""].filter(Boolean).join(" ")
            }
          >
            <span className="idx">{item.idx}</span>
            <span>{item.label}</span>
            <span className="chip" style={{ background: "rgba(212, 120, 74, 0.15)", color: "var(--filament)" }}>
              {item.phase}
            </span>
          </NavLink>
        ))}
      </nav>
      <p className="sidebar-foot">Phase 6 · Autonomous LangGraph Agent Live</p>
    </aside>
  );
}

