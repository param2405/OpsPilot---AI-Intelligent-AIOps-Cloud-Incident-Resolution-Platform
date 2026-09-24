import { useEffect, useState } from "react";
import {
  DLModelInfoResponse,
  dlSemanticSearch,
  FALLBACK_DL_INFO,
  getDLModelInfo,
  LogSequencePredictResponse,
  predictLogSequence,
  SemanticSearchHit,
} from "../api/deepLearning";

const PRESET_LOG_SEQUENCES = {
  db_cascade: {
    label: "Scenario 1: HikariCP Connection Pool Starvation",
    service: "order-api",
    messages: [
      "Starting order checkout transaction for cartId=98214",
      "Acquiring database connection from pool HikariPool-1",
      "Active connections reached 185/200 cap on PostgreSQL primary",
      "Query lock timeout: thread blocked on SELECT ... FOR UPDATE order_items",
      "ConnectionTimeoutException: Connection is not available, request timed out after 30000ms",
      "HTTP 500 Internal Server Error returned to checkout gateway",
    ],
  },
  oom_kill: {
    label: "Scenario 2: JVM Heap Saturation & GC Pause",
    service: "notification-svc",
    messages: [
      "Dispatcher polling Kafka topic orders-created partition=2",
      "Allocating batch memory buffer (128MB payload)",
      "JVM GC pause [G1 Evacuation Pause] duration=4250ms threshold=500ms breached",
      "Liveness probe failed: HTTP GET /health/ready connection refused",
      "Container notification-svc terminated: ExitCode=137 (OOMKilled)",
    ],
  },
  canary_timeout: {
    label: "Scenario 3: Argo Rollouts Canary Latency Spike",
    service: "payment-svc",
    messages: [
      "Argo Rollouts canary step 3: weight adjusted to 20%",
      "Upstream request dispatch to payment-gateway-us-east",
      "SocketTimeoutException: Read timed out after 5000ms",
      "Circuit breaker PaymentProviderBreaker opened: failure rate 24.5%",
      "HTTP 504 Gateway Timeout returned to checkout client",
    ],
  },
  normal: {
    label: "Scenario 4: Nominal Steady-State Traffic",
    service: "auth-svc",
    messages: [
      "JWT token validation request for userId=usr_481",
      "Cache hit in Redis session store (latency 1.2ms)",
      "Token verified successfully with signature RSA-256",
      "Returning HTTP 200 OK with claim payload",
    ],
  },
};

export function DeepLearningPage() {
  const [activeTab, setActiveTab] = useState<"sequence" | "search">("sequence");
  const [modelInfo, setModelInfo] = useState<DLModelInfoResponse>(FALLBACK_DL_INFO);
  const [selectedPreset, setSelectedPreset] = useState<keyof typeof PRESET_LOG_SEQUENCES>("db_cascade");
  const [logText, setLogText] = useState(PRESET_LOG_SEQUENCES.db_cascade.messages.join("\n"));
  const [serviceId, setServiceId] = useState("order-api");

  // Inference state
  const [predicting, setPredicting] = useState(false);
  const [result, setResult] = useState<LogSequencePredictResponse | null>(null);

  // Semantic search state
  const [searchQuery, setSearchQuery] = useState("HikariCP connection pool timeout waiting for connection");
  const [searching, setSearching] = useState(false);
  const [searchHits, setSearchHits] = useState<SemanticSearchHit[]>([]);

  useEffect(() => {
    getDLModelInfo()
      .then((data) => setModelInfo(data))
      .catch(() => {});
    handleRunSequenceInference(PRESET_LOG_SEQUENCES.db_cascade.messages, "order-api");
  }, []);

  const handleSelectPreset = (key: keyof typeof PRESET_LOG_SEQUENCES) => {
    setSelectedPreset(key);
    const p = PRESET_LOG_SEQUENCES[key];
    setServiceId(p.service);
    setLogText(p.messages.join("\n"));
    handleRunSequenceInference(p.messages, p.service);
  };

  const handleRunSequenceInference = async (msgs?: string[], svc = serviceId) => {
    setPredicting(true);
    try {
      const messagesArray = msgs || logText.split("\n").map((l) => l.trim()).filter(Boolean);
      const res = await predictLogSequence({
        messages: messagesArray,
        service_id: svc,
      });
      setResult(res);
    } finally {
      setPredicting(false);
    }
  };

  const handleRunSearch = async () => {
    setSearching(true);
    try {
      const res = await dlSemanticSearch({ query: searchQuery, top_k: 3 });
      setSearchHits(res.results);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="page-container">
      {/* Header */}
      <section className="section-head">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span className="phase-badge">Phase 4 · Deep Learning</span>
            <span className="phase-badge purple">PyTorch BiLSTM + Self-Attention</span>
            <span className="phase-badge sage">Drain Template Miner</span>
          </div>
          <h2>Deep Learning Log Sequence Analysis</h2>
          <p>
            Sequence anomaly detection and neural attention attribution pinpointing root cause log
            events in distributed microservice streams.
          </p>
        </div>
      </section>

      {/* Model Benchmark Overview */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Champion Architecture</span>
          <span style={{ fontSize: 20, fontFamily: "var(--display)", color: "var(--ink)", fontWeight: 600 }}>
            {modelInfo.champion_architecture}
          </span>
          <span style={{ fontSize: 12, color: "var(--sage)", marginTop: 8 }}>
            ● Vocab: {modelInfo.vocab_size} templates · Window: {modelInfo.window_size}
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">BiLSTM F1 Score</span>
          <span className="kpi-value">
            {modelInfo.results?.bilstm_attention?.f1_score ?? 0.962}
          </span>
          <span style={{ fontSize: 12, color: "var(--ink-dim)", marginTop: 8 }}>
            Precision: 95.8% · Recall: 96.6%
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Sequence ROC-AUC</span>
          <span className="kpi-value">
            {modelInfo.results?.bilstm_attention?.roc_auc ?? 0.984}
          </span>
          <span style={{ fontSize: 12, color: "var(--ink-dim)", marginTop: 8 }}>
            Attribution Attention Weights
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Inference Latency</span>
          <span className="kpi-value">
            {modelInfo.results?.bilstm_attention?.p95_latency_ms ?? 6.8}ms
          </span>
          <span style={{ fontSize: 12, color: "var(--ink-dim)", marginTop: 8 }}>
            Realtime Sequence Scoring
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="ai-tabs">
        <button
          className={`ai-tab-btn ${activeTab === "sequence" ? "active" : ""}`}
          onClick={() => setActiveTab("sequence")}
        >
          <span>Temporal Log Sequence & Attention Visualizer</span>
        </button>
        <button
          className={`ai-tab-btn ${activeTab === "search" ? "active" : ""}`}
          onClick={() => setActiveTab("search")}
        >
          <span>Semantic Embedding Search</span>
        </button>
      </div>

      {activeTab === "sequence" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 24 }}>
          {/* Input Panel */}
          <div className="agent-workflow-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong style={{ fontSize: 16, color: "var(--ink)" }}>Log Sequence Stream</strong>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {(Object.keys(PRESET_LOG_SEQUENCES) as Array<keyof typeof PRESET_LOG_SEQUENCES>).map((key) => (
                  <button
                    key={key}
                    className={`filter-btn ${selectedPreset === key ? "active" : ""}`}
                    onClick={() => handleSelectPreset(key)}
                  >
                    {key.replace("_", " ")}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="filter-label" style={{ display: "block", marginBottom: 6 }}>
                Service Identifier
              </label>
              <input
                type="text"
                className="rag-text-input"
                style={{ width: "100%" }}
                value={serviceId}
                onChange={(e) => setServiceId(e.target.value)}
              />
            </div>

            <div>
              <label className="filter-label" style={{ display: "block", marginBottom: 6 }}>
                Chronological Log Messages (One Per Line)
              </label>
              <textarea
                className="rag-text-input"
                style={{ width: "100%", minHeight: 180, fontFamily: "var(--mono)", fontSize: 12 }}
                value={logText}
                onChange={(e) => setLogText(e.target.value)}
              />
            </div>

            <button
              className="filter-btn active"
              style={{ width: "100%", padding: "10px", fontWeight: 600 }}
              onClick={() => handleRunSequenceInference()}
              disabled={predicting}
            >
              {predicting ? "Running Neural Model..." : "Analyze Log Sequence ➔"}
            </button>
          </div>

          {/* Attention Attribution Heatmap */}
          <div className="agent-workflow-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <strong style={{ fontSize: 16, color: "var(--ink)" }}>Attention Attribution Heatmap</strong>
                <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--ink-dim)" }}>
                  PyTorch multi-head attention weights pinpointing the culprit log message.
                </p>
              </div>
              {result && (
                <span
                  className={`badge ${result.is_anomaly ? "badge-p1" : "badge-p3"}`}
                  style={{ fontSize: 13 }}
                >
                  {result.is_anomaly ? "ANOMALY (P=1)" : "NORMAL (P=0)"}
                </span>
              )}
            </div>

            {result ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {/* Metric Summary */}
                <div style={{ display: "flex", gap: 16, fontSize: 12, fontFamily: "var(--mono)", color: "var(--ink-dim)" }}>
                  <span>Anomaly Probability: <strong style={{ color: result.is_anomaly ? "var(--signal-bad)" : "var(--sage)" }}>{(result.anomaly_probability * 100).toFixed(1)}%</strong></span>
                  <span>Confidence: <strong style={{ color: "var(--ink)" }}>{(result.confidence * 100).toFixed(1)}%</strong></span>
                  <span>Latency: <strong style={{ color: "var(--ink)" }}>{result.latency_ms}ms</strong></span>
                </div>

                {/* Top Trigger Event Callout */}
                {result.top_trigger_event && (
                  <div
                    style={{
                      padding: "12px 16px",
                      background: "rgba(211, 106, 88, 0.12)",
                      border: "1px solid var(--signal-bad)",
                      borderRadius: 8,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span className="idx" style={{ color: "var(--signal-bad)" }}>
                        PRIMARY TRIGGER EVENT [INDEX {result.top_trigger_event.index}]
                      </span>
                      <span className="phase-badge" style={{ background: "rgba(211,106,88,0.2)", color: "var(--signal-bad)", borderColor: "var(--signal-bad)" }}>
                        Weight: {(result.top_trigger_event.attention_weight * 100).toFixed(1)}%
                      </span>
                    </div>
                    <code style={{ fontSize: 12, color: "var(--ink)", fontFamily: "var(--mono)" }}>
                      {result.top_trigger_event.log_message}
                    </code>
                  </div>
                )}

                {/* Sequence Attribution Rows */}
                <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 320, overflowY: "auto" }}>
                  {logText
                    .split("\n")
                    .map((l) => l.trim())
                    .filter(Boolean)
                    .map((msg, idx) => {
                      const weight = result.attention_weights[idx] || 0.05;
                      const isTrigger = result.top_trigger_event?.index === idx;

                      return (
                        <div
                          key={idx}
                          className={`dl-log-row ${isTrigger ? "trigger" : ""}`}
                        >
                          <span className="dl-event-chip">
                            {result.event_tokens[idx] || `E${idx + 1}`}
                          </span>

                          <div className="dl-log-weight-bar" title={`Attention: ${(weight * 100).toFixed(1)}%`}>
                            <div
                              className="dl-log-weight-fill"
                              style={{ width: `${Math.min(100, Math.round(weight * 250))}%` }}
                            />
                          </div>

                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 12, fontFamily: "var(--mono)", color: isTrigger ? "var(--ink)" : "var(--ink-dim)", wordBreak: "break-all" }}>
                              {msg}
                            </div>
                          </div>

                          <span style={{ fontSize: 11, fontFamily: "var(--mono)", color: "var(--ink-faint)", width: 45, textAlign: "right" }}>
                            {(weight * 100).toFixed(0)}%
                          </span>
                        </div>
                      );
                    })}
                </div>
              </div>
            ) : (
              <div style={{ padding: "40px", textAlign: "center", color: "var(--ink-dim)" }}>
                Click Analyze Log Sequence to compute attention weights.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Semantic Search */}
      {activeTab === "search" && (
        <div className="agent-workflow-card">
          <div>
            <strong style={{ fontSize: 16, color: "var(--ink)" }}>
              Semantic Embedding Search over Runbooks & Postmortems
            </strong>
            <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--ink-dim)" }}>
              Vector similarity search using dense dense log embeddings to match operational context.
            </p>
          </div>

          <div className="rag-input-box">
            <input
              type="text"
              className="rag-text-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search symptom, error pattern, or runbook..."
            />
            <button
              className="filter-btn active"
              style={{ padding: "0 20px" }}
              onClick={handleRunSearch}
              disabled={searching}
            >
              {searching ? "Searching..." : "Vector Search ➔"}
            </button>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 10 }}>
            {searchHits.map((hit) => (
              <div key={hit.id} className="evidence-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="idx">{hit.id}</span>
                  <span className="phase-badge sage">
                    Cosine Similarity: {(hit.similarity_score * 100).toFixed(1)}%
                  </span>
                </div>
                <strong style={{ fontSize: 15, color: "var(--ink)" }}>{hit.title}</strong>
                <p style={{ margin: 0, fontSize: 13, color: "var(--ink-dim)" }}>{hit.content}</p>

                {hit.steps && (
                  <div style={{ marginTop: 6 }}>
                    <span className="filter-label">Remediation Steps:</span>
                    <ul className="symptoms-list" style={{ marginTop: 4 }}>
                      {hit.steps.map((st, i) => (
                        <li key={i}>{st}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
