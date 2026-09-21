import { useEffect, useState } from "react";
import { fetchLogs, fetchServices, LogEntry, Service } from "../api/observability";

export function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [selectedService, setSelectedService] = useState<string>("ALL");
  const [selectedLevel, setSelectedLevel] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [expandedLogId, setExpandedLogId] = useState<string | number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadServices() {
      const svcs = await fetchServices();
      setServices(svcs);
    }
    loadServices();
  }, []);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      const res = await fetchLogs({
        service_id: selectedService !== "ALL" ? selectedService : undefined,
        log_level: selectedLevel !== "ALL" ? selectedLevel : undefined,
        search: searchQuery || undefined,
      });
      setLogs(res);
      setLoading(false);
    }
    loadData();
  }, [selectedService, selectedLevel, searchQuery]);

  return (
    <div className="page-container">
      {/* Search & Filter Controls */}
      <section className="filter-bar">
        <input
          type="text"
          className="search-input"
          placeholder="Filter by keyword, exception, or token (e.g. timeout, connection, pool)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />

        <div className="filter-group">
          <span className="filter-label">Level:</span>
          {["ALL", "ERROR", "WARN", "INFO", "DEBUG"].map((lvl) => (
            <button
              key={lvl}
              onClick={() => setSelectedLevel(lvl)}
              className={`filter-btn ${selectedLevel === lvl ? "active" : ""}`}
            >
              {lvl}
            </button>
          ))}
        </div>

        <div className="filter-group">
          <span className="filter-label">Service:</span>
          <select
            className="select-input"
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
          >
            <option value="ALL">All Microservices</option>
            {services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
      </section>

      {/* Log Console Terminal */}
      <section className="log-console">
        <div className="log-console-header">
          <div>
            <span>DISTRIBUTED STREAM CONSOLE</span>
            <span style={{ marginLeft: 12, color: "var(--ink)" }}>
              {logs.length} events ingested
            </span>
          </div>
          <div style={{ display: "flex", gap: 16 }}>
            <span>AUTOSCROLL: LOCKED</span>
            <span>INGESTION: ACTIVE</span>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: "32px", textAlign: "center", color: "var(--ink-dim)" }}>
            Streaming log telemetry...
          </div>
        ) : logs.length === 0 ? (
          <div style={{ padding: "48px", textAlign: "center", color: "var(--ink-dim)" }}>
            No log events found matching query filters.
          </div>
        ) : (
          <div className="log-entries-list">
            {logs.map((log) => {
              const isExpanded = expandedLogId === log.id;
              return (
                <div key={log.id}>
                  <div
                    className="log-item"
                    style={{ cursor: "pointer" }}
                    onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                  >
                    <span className="log-time">
                      {new Date(log.timestamp).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </span>

                    <span className="log-svc" title={log.service_id}>
                      {log.service_id}
                    </span>

                    <span className={`log-lvl ${log.log_level}`}>{log.log_level}</span>

                    <span className="log-msg">{log.message}</span>

                    {log.trace_id ? (
                      <span className="log-trace" title={`Trace ID: ${log.trace_id}`}>
                        {log.trace_id.slice(0, 11)}...
                      </span>
                    ) : (
                      <span />
                    )}
                  </div>

                  {isExpanded && log.context_data && (
                    <div
                      style={{
                        padding: "10px 18px 14px 170px",
                        background: "rgba(0, 0, 0, 0.4)",
                        borderBottom: "1px solid var(--line)",
                        fontSize: "11px",
                      }}
                    >
                      <div style={{ color: "var(--ink-faint)", marginBottom: 4 }}>
                        METADATA CONTEXT PAYLOAD:
                      </div>
                      <pre
                        style={{
                          margin: 0,
                          color: "var(--sage)",
                          fontFamily: "var(--mono)",
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {JSON.stringify(log.context_data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
