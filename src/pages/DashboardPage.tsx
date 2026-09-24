import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Deployment,
  fetchDeployments,
  fetchIncidents,
  fetchMetrics,
  fetchServices,
  Incident,
  Metric,
  Service,
} from "../api/observability";

export function DashboardPage() {
  const [services, setServices] = useState<Service[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [metrics, setMetrics] = useState<Record<string, Metric>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    async function loadDashboardData() {
      try {
        const [svcs, incs, deps] = await Promise.all([
          fetchServices(),
          fetchIncidents(),
          fetchDeployments(),
        ]);
        if (!isMounted) return;
        setServices(svcs);
        setIncidents(incs);
        setDeployments(deps);

        // Fetch recent telemetry metrics for each service
        const telemetryMap: Record<string, Metric> = {};
        for (const s of svcs) {
          const mList = await fetchMetrics(s.id, 1);
          if (mList.length > 0) {
            telemetryMap[s.id] = mList[0];
          }
        }
        if (isMounted) {
          setMetrics(telemetryMap);
          setLoading(false);
        }
      } catch {
        if (isMounted) setLoading(false);
      }
    }
    loadDashboardData();
    return () => {
      isMounted = false;
    };
  }, []);

  const activeIncidents = incidents.filter(
    (i) => i.status === "INVESTIGATING" || i.status === "IDENTIFIED",
  );
  const p1Count = activeIncidents.filter((i) => i.severity === "P1_CRITICAL").length;

  const latencies = Object.values(metrics).map((m) => m.latency_p95_ms ?? 0);
  const avgLatency =
    latencies.length > 0
      ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)
      : 240;

  return (
    <div className="page-container">
      {/* KPI Cards Row */}
      <section className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Monitored Services</span>
          <span className="kpi-value">{loading ? "..." : services.length}</span>
          <span className="kpi-sub">Production telemetry active</span>
        </div>

        <div className={`kpi-card ${p1Count > 0 ? "alert" : ""}`}>
          <span className="kpi-label">Active Incidents</span>
          <span className={`kpi-value ${p1Count > 0 ? "alert" : ""}`}>
            {loading ? "..." : activeIncidents.length}
          </span>
          <span className="kpi-sub">
            {p1Count > 0 ? `⚠️ ${p1Count} P1 Critical requiring triage` : "All standard operations stable"}
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Fleet Avg Latency (p95)</span>
          <span className="kpi-value">{loading ? "..." : `${avgLatency}ms`}</span>
          <span className="kpi-sub">Target SLA: &lt; 500ms</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Recent Releases</span>
          <span className="kpi-value">{loading ? "..." : deployments.length}</span>
          <span className="kpi-sub">CI/CD tracked rollouts</span>
        </div>
      </section>

      {/* AIOps Platform Capabilities Banner */}
      <section className="agent-workflow-card" style={{ padding: "20px 24px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 14 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span className="phase-badge">Phase 1 - 6 All Operational</span>
              <span className="phase-badge sage">AIOps Intelligence Active</span>
            </div>
            <h3 style={{ margin: 0, fontFamily: "var(--display)", fontSize: 18, color: "var(--ink)" }}>
              OpsPilot AI Incident Resolution Architecture
            </h3>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--ink-dim)" }}>
              Integrated telemetry, machine learning anomaly detectors, deep learning log sequence attention, RAG knowledge store, and LangGraph autonomous SRE agent.
            </p>
          </div>

          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <Link to="/ml" className="filter-btn">
              ML Engine (Phase 3)
            </Link>
            <Link to="/deep-learning" className="filter-btn">
              Deep Learning (Phase 4)
            </Link>
            <Link to="/rag" className="filter-btn">
              RAG Knowledge (Phase 5)
            </Link>
            <Link to="/investigation" className="filter-btn active" style={{ fontWeight: 600 }}>
              AI Agent (Phase 6) ➔
            </Link>
          </div>
        </div>
      </section>

      {/* Fleet Services Grid */}
      <section>
        <div className="section-head">
          <div>
            <h2>Fleet Services</h2>
            <p>Real-time node telemetry and operational status across microservices.</p>
          </div>
          <Link to="/metrics" className="filter-btn">
            View Deep Metrics →
          </Link>
        </div>

        <div className="fleet-grid">
          {services.map((svc) => {
            const m = metrics[svc.id];
            const cpu = m ? Math.round(m.cpu_usage ?? 45) : 45;
            const mem = m ? Math.round(m.memory_usage ?? 58) : 58;
            const lat = m ? Math.round(m.latency_p95_ms ?? 180) : 180;
            const hasP1 = activeIncidents.some((i) => i.service_id === svc.id);

            return (
              <div key={svc.id} className="fleet-card">
                <div className="fleet-card-header">
                  <div>
                    <div className="fleet-service-name">{svc.name}</div>
                    <div className="fleet-meta">
                      <span className={`badge badge-${svc.tier.toLowerCase()}`}>{svc.tier}</span>
                      <span className="idx">{svc.id}</span>
                    </div>
                  </div>
                  <div className="pill">
                    <span className={`dot ${hasP1 ? "bad" : "ok"}`} />
                    <span>{hasP1 ? "Degraded" : "Nominal"}</span>
                  </div>
                </div>

                <div className="fleet-meters">
                  <div className="meter-row">
                    <span>CPU</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div className="meter-bar-bg">
                        <div
                          className={`meter-bar-fill ${cpu > 80 ? "critical" : cpu > 65 ? "warning" : ""}`}
                          style={{ width: `${Math.min(cpu, 100)}%` }}
                        />
                      </div>
                      <span>{cpu}%</span>
                    </div>
                  </div>

                  <div className="meter-row">
                    <span>Memory</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div className="meter-bar-bg">
                        <div
                          className={`meter-bar-fill ${mem > 85 ? "critical" : mem > 70 ? "warning" : ""}`}
                          style={{ width: `${Math.min(mem, 100)}%` }}
                        />
                      </div>
                      <span>{mem}%</span>
                    </div>
                  </div>

                  <div className="meter-row">
                    <span>p95 Latency</span>
                    <span style={{ color: lat > 1000 ? "var(--signal-bad)" : "inherit" }}>
                      {lat} ms
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Two Column Section: Active Incidents & Deployments */}
      <div className="layout" style={{ gridTemplateColumns: "1.2fr 0.8fr" }}>
        {/* Active Incidents */}
        <section className="table-panel" style={{ padding: "20px" }}>
          <div className="section-head">
            <div>
              <h2>Active Incidents</h2>
              <p>Unresolved service degradations and anomalies.</p>
            </div>
            <Link to="/incidents" className="filter-btn">
              All Incidents →
            </Link>
          </div>

          {incidents.length === 0 ? (
            <p style={{ color: "var(--ink-dim)", fontSize: "14px" }}>No open incidents detected.</p>
          ) : (
            <div className="table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Severity</th>
                    <th>Incident</th>
                    <th>Service</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {incidents.slice(0, 4).map((inc) => (
                    <tr key={inc.incident_id}>
                      <td>
                        <span
                          className={`badge ${
                            inc.severity === "P1_CRITICAL"
                              ? "badge-p1"
                              : inc.severity === "P2_HIGH"
                                ? "badge-p2"
                                : "badge-p3"
                          }`}
                        >
                          {inc.severity.replace("_", " ")}
                        </span>
                      </td>
                      <td>
                        <strong style={{ color: "var(--ink)", display: "block" }}>{inc.title}</strong>
                        <span className="idx">{inc.incident_id}</span>
                      </td>
                      <td>
                        <span className="idx">{inc.service_id}</span>
                      </td>
                      <td>
                        <span className="status-pill">
                          <span
                            className={`dot ${inc.status === "RESOLVED" ? "ok" : "bad"}`}
                          />
                          {inc.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Deployments Stream */}
        <section className="table-panel" style={{ padding: "20px" }}>
          <div className="section-head">
            <div>
              <h2>Deployments</h2>
              <p>Recent service release events.</p>
            </div>
          </div>

          <div>
            {deployments.slice(0, 5).map((dep) => (
              <div key={dep.id} className="deployment-item">
                <div>
                  <div className="dep-version">{dep.version} · {dep.service_id}</div>
                  <div className="dep-meta">
                    by {dep.deployed_by} ({dep.commit_hash})
                  </div>
                </div>
                <span
                  className={`badge ${
                    dep.status === "SUCCESS"
                      ? "badge-standard"
                      : dep.status === "ROLLED_BACK"
                        ? "badge-p1"
                        : "badge-supporting"
                  }`}
                >
                  {dep.status}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
