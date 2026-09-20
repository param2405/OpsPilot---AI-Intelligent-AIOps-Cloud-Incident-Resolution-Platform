import { NavLink } from "react-router-dom";
import { Mark } from "../brand/Mark";

const items = [
  { to: "/", label: "Foundation", idx: "01", later: false },
  { to: "/dashboard", label: "Dashboard", idx: "02", later: true },
  { to: "/incidents", label: "Incidents", idx: "03", later: true },
  { to: "/metrics", label: "Metrics", idx: "04", later: true },
  { to: "/logs", label: "Logs", idx: "05", later: true },
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
          <span>OP-01 / FOUNDATION</span>
        </div>
      </div>
      <p className="nav-label">Surfaces</p>
      <nav className="nav" aria-label="Primary">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
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
      <p className="sidebar-foot">Phase 1 · no models wired</p>
    </aside>
  );
}
