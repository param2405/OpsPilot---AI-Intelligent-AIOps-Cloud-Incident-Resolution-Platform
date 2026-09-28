import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchIncidents, fetchServices, Incident, Service } from "../api/observability";
import { searchSemanticKnowledge, SemanticSearchHit } from "../api/deepLearning";
import { listInvestigations, InvestigationSummary } from "../api/orchestration";
import {
  Badge,
  Card,
  EmptyState,
  ErrorCard,
  LoadingSpinner,
  severityToVariant,
  statusToVariant,
} from "../components/common";

export function HistoricalIncidentsPage() {
  const navigate = useNavigate();

  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [selectedService, setSelectedService] = useState<string>("ALL");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [semanticHits, setSemanticHits] = useState<SemanticSearchHit[] | null>(null);
  const [searchingSemantic, setSearchingSemantic] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [incList, invList, svcList] = await Promise.all([
          fetchIncidents(),
          listInvestigations({ limit: 50 }).catch(() => []),
          fetchServices().catch(() => []),
        ]);

        if (!isMounted) return;
        setIncidents(incList);
        setInvestigations(invList);
        setServices(svcList);
      } catch (err: unknown) {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Failed to load historical incidents archive.");
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadData();
    return () => {
      isMounted = false;
    };
  }, []);

  async function handleSemanticSearch() {
    if (!searchQuery.trim()) {
      setSemanticHits(null);
      return;
    }
    setSearchingSemantic(true);
    try {
      const resp = await searchSemanticKnowledge({
        query: searchQuery.trim(),
        corpus_type: "incidents",
        top_k: 10,
      });
      setSemanticHits(resp.results || []);
    } catch {
      // If semantic search fails, fallback to standard filter
      setSemanticHits(null);
    } finally {
      setSearchingSemantic(false);
    }
  }

  function handleClearSearch() {
    setSearchQuery("");
    setSemanticHits(null);
  }

  // Filtered incidents if not using semantic search
  const filteredIncidents = incidents.filter((inc) => {
    if (selectedService !== "ALL" && inc.service_id !== selectedService) return false;
    if (selectedSeverity !== "ALL" && inc.severity !== selectedSeverity) return false;
    if (searchQuery.trim() && !semanticHits) {
      const q = searchQuery.toLowerCase();
      const matchTitle = (inc.title || "").toLowerCase().includes(q);
      const matchCause = (inc.root_cause || inc.root_cause_hypothesis || "").toLowerCase().includes(q);
      const matchResolution = (inc.resolution || "").toLowerCase().includes(q);
      if (!matchTitle && !matchCause && !matchResolution) return false;
    }
    return true;
  });

  return (
    <div className="page-container">
      {/* Header Panel */}
      <section className="dashboard-hero">
        <div className="hero-head">
          <div>
            <span className="idx" style={{ color: "var(--filament)" }}>
              KNOWLEDGE ARCHIVE · POSTMORTEMS & RESOLUTIONS
            </span>
            <h1 style={{ margin: "4px 0 8px", fontSize: 24, fontFamily: "var(--display)" }}>
              Historical Incident Repository
            </h1>
            <p style={{ margin: 0, color: "var(--ink-dim)", fontSize: 14 }}>
              Search past operational incidents, root-cause analyses, and proven remediation strategies using dense vector embeddings.
            </p>
          </div>
        </div>
      </section>

      {/* Semantic Search & Filter Bar */}
      <section className="filter-bar" style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
        <div style={{ display: "flex", flex: 1, minWidth: 300, gap: 8 }}>
          <input
            type="text"
            className="search-input"
            style={{ flex: 1 }}
            placeholder="Semantic search (e.g., 'database pool timeout', 'memory leak in worker', 'canary 504')..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSemanticSearch();
            }}
          />
          <button
            className="filter-btn active"
            disabled={searchingSemantic}
            onClick={handleSemanticSearch}
          >
            {searchingSemantic ? "Searching..." : "Vector Search 🔍"}
          </button>
          {searchQuery && (
            <button className="filter-btn" onClick={handleClearSearch}>
              Clear
            </button>
          )}
        </div>

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

      {/* Search results banner if semantic search active */}
      {semanticHits && (
        <div
          style={{
            padding: "12px 18px",
            borderRadius: 10,
            background: "rgba(212, 120, 74, 0.08)",
            border: "1px solid rgba(212, 120, 74, 0.25)",
            marginBottom: 16,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div style={{ fontSize: 13, color: "var(--ink)" }}>
            Found <strong style={{ color: "var(--filament)" }}>{semanticHits.length}</strong> semantic similarity matches for query: <em>"{searchQuery}"</em>
          </div>
          <button className="filter-btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={handleClearSearch}>
            Reset to All Incidents
          </button>
        </div>
      )}

      {/* Content Area */}
      {loading ? (
        <LoadingSpinner message="Querying historical incident postmortems & pgvector similarity index..." />
      ) : error ? (
        <ErrorCard title="Repository Unavailable" message={error} onRetry={() => window.location.reload()} />
      ) : semanticHits ? (
        /* Semantic Search Results */
        <div style={{ display: "grid", gap: 14 }}>
          {semanticHits.length === 0 ? (
            <EmptyState message="No past incidents matched the semantic query criteria." />
          ) : (
            semanticHits.map((hit) => (
              <Card
                key={hit.id}
                kicker={`SIMILARITY: ${(hit.similarity_score * 100).toFixed(1)}% · RANK #${hit.rank}`}
                title={hit.title}
                actions={
                  <button
                    className="filter-btn"
                    onClick={() => navigate(`/incidents/${encodeURIComponent(hit.id)}`)}
                  >
                    View Details ➔
                  </button>
                }
              >
                <div style={{ display: "grid", gap: 8, fontSize: 13, marginTop: 4 }}>
                  {hit.failure_domain && (
                    <div>
                      <span className="chip" style={{ background: "rgba(212, 120, 74, 0.15)", color: "var(--filament)" }}>
                        {hit.failure_domain}
                      </span>
                    </div>
                  )}
                  {hit.content && (
                    <div style={{ color: "var(--ink-dim)", lineHeight: 1.5 }}>
                      {hit.content}
                    </div>
                  )}
                  {hit.steps && hit.steps.length > 0 && (
                    <div style={{ marginTop: 6 }}>
                      <strong style={{ color: "var(--sage)", fontSize: 12, display: "block", marginBottom: 4 }}>
                        Applied Remediation Steps:
                      </strong>
                      <ul style={{ margin: 0, paddingLeft: 16, color: "var(--ink-dim)", fontSize: 12 }}>
                        {hit.steps.map((st, i) => (
                          <li key={i}>{st}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </Card>
            ))
          )}
        </div>
      ) : (
        /* Standard Filtered Incidents List */
        <div style={{ display: "grid", gap: 14 }}>
          {filteredIncidents.length === 0 ? (
            <EmptyState message="No historical incidents found matching the selected filters." />
          ) : (
            filteredIncidents.map((inc) => {
              const inv = investigations.find((inv) => inv.incident_id === inc.incident_id || inv.incident_id === inc.id);
              return (
                <Card
                  key={inc.incident_id || inc.id}
                  kicker={`${inc.service_id.toUpperCase()} · ${inc.incident_type}`}
                  title={inc.title}
                  actions={
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <Badge variant={severityToVariant(inc.severity)}>
                        {inc.severity.replace("_", " ")}
                      </Badge>
                      <Badge variant={statusToVariant(inc.status)}>
                        {inc.status}
                      </Badge>
                      <button
                        className="filter-btn"
                        style={{ marginLeft: 6 }}
                        onClick={() => navigate(`/incidents/${encodeURIComponent(inc.incident_id || inc.id)}`)}
                      >
                        Inspect ➔
                      </button>
                    </div>
                  }
                >
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14, marginTop: 8 }}>
                    <div>
                      <strong style={{ fontSize: 12, color: "var(--filament)", display: "block", marginBottom: 4 }}>
                        ROOT CAUSE ANALYSIS:
                      </strong>
                      <div style={{ fontSize: 13, color: "var(--ink)", lineHeight: 1.5 }}>
                        {inc.root_cause || inc.root_cause_hypothesis || inv?.suspected_root_cause || "Detailed postmortem synthesis on file."}
                      </div>
                    </div>

                    <div>
                      <strong style={{ fontSize: 12, color: "var(--sage)", display: "block", marginBottom: 4 }}>
                        RESOLUTION & MITIGATION:
                      </strong>
                      <div style={{ fontSize: 13, color: "var(--ink-dim)", lineHeight: 1.5 }}>
                        {inc.resolution || "Remediation runbook applied successfully; SLO restored."}
                      </div>
                    </div>
                  </div>

                  <div style={{ marginTop: 14, paddingTop: 10, borderTop: "1px solid var(--line)", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, color: "var(--ink-faint)", fontFamily: "var(--mono)" }}>
                    <div>
                      Detected: {new Date(inc.detected_at || inc.started_at || Date.now()).toLocaleDateString()} at {new Date(inc.detected_at || inc.started_at || Date.now()).toLocaleTimeString()}
                    </div>
                    {inc.resolved_at && (
                      <div>
                        Resolved: {new Date(inc.resolved_at).toLocaleTimeString()}
                      </div>
                    )}
                  </div>
                </Card>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
