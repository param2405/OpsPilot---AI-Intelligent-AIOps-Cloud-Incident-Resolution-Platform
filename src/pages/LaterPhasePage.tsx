import { Link, useLocation } from "react-router-dom";

const titles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/incidents": "Incidents",
  "/metrics": "Metrics",
  "/logs": "Logs",
  "/investigation": "AI investigation",
  "/recommendations": "Recommendations",
  "/settings": "Settings",
};

export function LaterPhasePage() {
  const { pathname } = useLocation();
  const title = titles[pathname] ?? "Later surface";

  return (
    <section className="later">
      <p className="kicker">Not in Phase 1</p>
      <h1>{title}</h1>
      <p>
        This route exists so the information architecture is visible now. It does not load
        incident data, metrics, or model output. Those land in later phases.
      </p>
      <p>
        <Link to="/">Return to foundation</Link>
      </p>
    </section>
  );
}
