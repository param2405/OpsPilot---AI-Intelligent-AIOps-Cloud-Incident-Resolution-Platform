import { NavLink } from "react-router-dom";
import { Mark } from "../brand/Mark";

const corePages = [
  { to: "/", label: "Dashboard", idx: "01", chip: "P8" },
  { to: "/incidents", label: "Incidents", idx: "02", chip: "P8" },
  { to: "/remediation", label: "Remediation & HITL", idx: "09", chip: "P9" },
  { to: "/metrics", label: "Metrics", idx: "03", chip: "P8" },
  { to: "/logs", label: "Logs", idx: "04", chip: "P8" },
  { to: "/investigation", label: "AI Investigation", idx: "05", chip: "P8" },
  { to: "/historical-incidents", label: "Historical Incidents", idx: "06", chip: "P8" },
  { to: "/model-performance", label: "Model Performance", idx: "07", chip: "P8" },
  { to: "/system-health", label: "System Health", idx: "08", chip: "P8" },
];

const subsystemExplorers = [
  { to: "/foundation", label: "Foundation", idx: "F1", chip: "P1" },
  { to: "/ml", label: "ML Engine", idx: "M3", chip: "P3" },
  { to: "/deep-learning", label: "Deep Learning", idx: "D4", chip: "P4" },
  { to: "/rag", label: "RAG Knowledge", idx: "R5", chip: "P5" },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <Mark />
        <div className="brand-copy">
          <strong>OpsPilot AI</strong>
          <span>OP-08 / PRODUCTION DASHBOARD</span>
        </div>
      </div>

      <p className="nav-label">Core Operations</p>
      <nav className="nav" aria-label="Primary Core">
        {corePages.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            <span className="idx">{item.idx}</span>
            <span>{item.label}</span>
            <span className="chip" style={{ background: "rgba(212, 120, 74, 0.15)", color: "var(--filament)" }}>
              {item.chip}
            </span>
          </NavLink>
        ))}
      </nav>

      <p className="nav-label" style={{ marginTop: 16 }}>
        Subsystems
      </p>
      <nav className="nav" aria-label="Subsystems">
        {subsystemExplorers.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            <span className="idx">{item.idx}</span>
            <span>{item.label}</span>
            <span className="chip" style={{ background: "rgba(143, 191, 159, 0.15)", color: "var(--sage)" }}>
              {item.chip}
            </span>
          </NavLink>
        ))}
      </nav>

      <p className="sidebar-foot">Phase 6 · Autonomous LangGraph Agent Live</p>
      <p className="sidebar-foot" style={{ marginTop: 2 }}>Phase 9 · Human-In-The-Loop Remediation Active</p>
    </aside>
  );
}
