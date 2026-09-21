import { useEffect, useState } from "react";
import { fetchIncidents, fetchServices, Incident, Service } from "../api/observability";

export function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [selectedSeverity, setSelectedSeverity] = useState<string>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [selectedService, setSelectedService] = useState<string>("ALL");
  const [activeIncident, setActiveIncident] = useState<Incident | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [incList, svcList] = await Promise.all([fetchIncidents(), fetchServices()]);
      setIncidents(incList);
      setServices(svcList);
      setLoading(false);
    }
    load();
  }, []);

  const filteredIncidents = incidents.filter((inc) => {
    if (selectedSeverity !== "ALL" && inc.severity !== selectedSeverity) return false;
    if (selectedStatus !== "ALL" && inc.status !== selectedStatus) return false;
    if (selectedService !== "ALL" && inc.service_id !== selectedService) return false;
    return true;
  });

  return (
    <div className="page-container">
      {/* Filter Bar */}
      <section className="filter-bar">
        <div className="filter-group">
          <span className="filter-label">Severity:</span>
          {["ALL", "P1_CRITICAL", "P2_HIGH", "P3_MEDIUM"].map((sev) => (
            <button
              key={sev}
              onClick={() => setSelectedSeverity(sev)}
              className={`filter-btn ${selectedSeverity === sev ? "active" : ""}`}
            >
              {sev.replace("_", " ")}
            </button>
          ))}
        </div>

        <div className="filter-group">
          <span className="filter-label">Status:</span>
          {["ALL", "INVESTIGATING", "IDENTIFIED", "MITIGATED", "RESOLVED"].map((st) => (
            <button
              key={st}
              onClick={() => setSelectedStatus(st)}
              className={`filter-btn ${selectedStatus === st ? "active" : ""}`}
            >
              {st}
            </button>
          ))}
        </div>

        <div className="filter-group" style={{ marginLeft: "auto" }}>
          <span className="filter-label">Service:</span>
          <select
            className="select-input"
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
          >
            <option value="ALL">All Services</option>
            {services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.id})
              </option>
            ))}
          </select>
        </div>
      </section>

      {/* Incidents Table */}
      <section className="table-panel">
        <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--line)" }}>
          <div className="section-head" style={{ marginBottom: 0 }}>
            <div>
              <h2>Incident Registry ({filteredIncidents.length})</h2>
              <p>Click any incident row to inspect root-cause hypothesis and telemetry indicators.</p>
            </div>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: "32px", textAlign: "center", color: "var(--ink-dim)" }}>
            Loading incidents...
          </div>
        ) : filteredIncidents.length === 0 ? (
          <div style={{ padding: "48px", textAlign: "center", color: "var(--ink-dim)" }}>
            No incidents found matching the selected filters.
          </div>
        ) : (
          <div className="table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>ID</th>
                  <th>Title</th>
                  <th>Service</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Detected</th>
                </tr>
              </thead>
              <tbody>
                {filteredIncidents.map((inc) => (
                  <tr
                    key={inc.incident_id}
                    className="clickable"
                    onClick={() => setActiveIncident(inc)}
                  >
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
                      <span className="idx">{inc.incident_id}</span>
                    </td>
                    <td>
                      <strong style={{ color: "var(--ink)" }}>{inc.title}</strong>
                    </td>
                    <td>
                      <span className="idx">{inc.service_id}</span>
                    </td>
                    <td>
                      <span className="idx">{inc.incident_type}</span>
                    </td>
                    <td>
                      <span className="status-pill">
                        <span className={`dot ${inc.status === "RESOLVED" ? "ok" : "bad"}`} />
                        {inc.status}
                      </span>
                    </td>
                    <td>
                      <span className="idx">
                        {new Date(
                          inc.detected_at || inc.started_at || Date.now(),
                        ).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Incident Detail Drawer */}
      {activeIncident && (
        <div className="modal-overlay" onClick={() => setActiveIncident(null)}>
          <div className="incident-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div>
                <span
                  className={`badge ${
                    activeIncident.severity === "P1_CRITICAL"
                      ? "badge-p1"
                      : activeIncident.severity === "P2_HIGH"
                        ? "badge-p2"
                        : "badge-p3"
                  }`}
                >
                  {activeIncident.severity.replace("_", " ")}
                </span>
                <span className="idx" style={{ marginLeft: 8 }}>
                  {activeIncident.incident_id}
                </span>
                <h3>{activeIncident.title}</h3>
              </div>
              <button
                className="close-btn"
                onClick={() => setActiveIncident(null)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div className="drawer-block">
              <span className="drawer-label">Affected Microservice</span>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <strong style={{ fontSize: 16 }}>{activeIncident.service_id}</strong>
                <span className="badge badge-standard">{activeIncident.incident_type}</span>
              </div>
            </div>

            <div className="drawer-block">
              <span className="drawer-label">Current Lifecycle Status</span>
              <div className="status-pill" style={{ fontSize: 14 }}>
                <span
                  className={`dot ${activeIncident.status === "RESOLVED" ? "ok" : "bad"}`}
                />
                {activeIncident.status}
              </div>
            </div>

            <div className="drawer-block">
              <span className="drawer-label">Observed Symptoms</span>
              <ul className="symptoms-list">
                {(Array.isArray(activeIncident.symptoms)
                  ? activeIncident.symptoms
                  : [activeIncident.symptoms]
                ).map((symptom: string, idx: number) => (
                  <li key={idx}>{symptom}</li>
                ))}
              </ul>
            </div>

            <div className="drawer-block">
              <span className="drawer-label">Root Cause Hypothesis</span>
              <div className="root-cause-box">
                {activeIncident.root_cause_hypothesis ||
                  activeIncident.root_cause ||
                  "Hypothesis synthesis in progress by root-cause agent..."}
              </div>
            </div>

            <div className="drawer-block">
              <span className="drawer-label">Timeline</span>
              <div style={{ display: "grid", gap: 8, fontSize: 13, fontFamily: "var(--mono)" }}>
                <div>
                  <span style={{ color: "var(--ink-faint)" }}>Detected: </span>
                  {new Date(
                    activeIncident.detected_at || activeIncident.started_at || Date.now(),
                  ).toLocaleString()}
                </div>
                {activeIncident.mitigated_at && (
                  <div>
                    <span style={{ color: "var(--ink-faint)" }}>Mitigated: </span>
                    {new Date(activeIncident.mitigated_at).toLocaleString()}
                  </div>
                )}
                {activeIncident.resolved_at && (
                  <div>
                    <span style={{ color: "var(--ink-faint)" }}>Resolved: </span>
                    {new Date(activeIncident.resolved_at).toLocaleString()}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
