import { NavLink } from "react-router-dom";
import { Mark } from "../brand/Mark";

const items = [
  { to: "/foundation", label: "Foundation", idx: "01", later: false },
  { to: "/", label: "Dashboard", idx: "02", later: false },
  { to: "/incidents", label: "Incidents", idx: "03", later: false },
  { to: "/metrics", label: "Metrics", idx: "04", later: false },
  { to: "/logs", label: "Logs", idx: "05", later: false },
  { to: "/investigation", label: "AI investigation", idx: "06", later: true },
  { to: "/recommendations", label: "Recommendations", idx: "07", later: true },
  { to: "/settings", label: "Settings", idx: "08", later: true },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <Mark />
        <div className="brand-copy">
          <strong>OpsPilot AI</strong>
          <span>OP-02 / OBSERVABILITY</span>
        </div>
      </div>
      <p className="nav-label">Surfaces</p>
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
            {item.later ? <span className="chip">Later</span> : <span />}
          </NavLink>
        ))}
      </nav>
      <p className="sidebar-foot">Phase 2 · Telemetry & Ingestion Live</p>
    </aside>
  );
}
