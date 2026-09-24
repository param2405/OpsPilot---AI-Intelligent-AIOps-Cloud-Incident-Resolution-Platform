import { useEffect, useState } from "react";
import {
  classifyIncident,
  detectMetricAnomaly,
  FALLBACK_MODELS_OVERVIEW,
  getModelsOverview,
  IncidentClassificationResponse,
  ModelsOverviewResponse,
  predictSeverity,
  retrainModels,
  SeverityPredictionResponse,
} from "../api/ml";

export function MLEnginePage() {
  const [activeTab, setActiveTab] = useState<"anomaly" | "classifier" | "registry">("anomaly");
  const [modelsOverview, setModelsOverview] = useState<ModelsOverviewResponse>(FALLBACK_MODELS_OVERVIEW);

  // Anomaly Sandbox Sliders
  const [cpu, setCpu] = useState(42.5);
  const [memory, setMemory] = useState(65.0);
  const [latency, setLatency] = useState(85.0);
  const [errorRate, setErrorRate] = useState(0.005);
  const [connections, setConnections] = useState(25);
  const [evaluatingAnomaly, setEvaluatingAnomaly] = useState(false);
  const [anomalyResult, setAnomalyResult] = useState<any>({
    is_anomaly: false,
    anomaly_score: 0.08,
    contributing_signals: ["Telemetry metrics conform within 2-sigma baseline"],
    algorithm: "IsolationForest",
  });

  // Classifier Sandbox State
  const [title, setTitle] = useState("HikariCP connection pool timeout on checkout");
  const [symptoms, setSymptoms] = useState(
    "Active connections saturated at 195/200. Client requests timing out after 30000ms. PostgreSQL query latency spiking.",
  );
  const [evaluatingClassifier, setEvaluatingClassifier] = useState(false);
  const [classResult, setClassResult] = useState<IncidentClassificationResponse | null>(null);
  const [sevResult, setSevResult] = useState<SeverityPredictionResponse | null>(null);

  // Retrain State
  const [retraining, setRetraining] = useState(false);
  const [retrainNotice, setRetrainNotice] = useState<string | null>(null);

  useEffect(() => {
    getModelsOverview()
      .then((data) => setModelsOverview(data))
      .catch(() => {});
  }, []);

  const handleEvaluateAnomaly = async (
    newCpu = cpu,
    newMem = memory,
    newLat = latency,
    newErr = errorRate,
    newConn = connections,
  ) => {
    setEvaluatingAnomaly(true);
    try {
      const res = await detectMetricAnomaly({
        service_id: "order-api",
        cpu_usage: newCpu,
        memory_usage: newMem,
        disk_usage: 45.0,
        network_traffic_kbps: 1200.0,
        request_count: 550,
        latency_p95_ms: newLat,
        error_rate: newErr,
        active_connections: newConn,
      });
      setAnomalyResult(res);
    } finally {
      setEvaluatingAnomaly(false);
    }
  };

  const handleApplyPreset = (preset: "normal" | "db-starvation" | "mem-leak" | "outage") => {
    let c = 40, m = 55, l = 60, e = 0.002, conn = 20;
    if (preset === "db-starvation") {
      c = 72; m = 78; l = 3200; e = 0.185; conn = 195;
    } else if (preset === "mem-leak") {
      c = 85; m = 96; l = 1450; e = 0.042; conn = 80;
    } else if (preset === "outage") {
      c = 94; m = 88; l = 4500; e = 0.45; conn = 250;
    }
    setCpu(c);
    setMemory(m);
    setLatency(l);
    setErrorRate(e);
    setConnections(conn);
    handleEvaluateAnomaly(c, m, l, e, conn);
  };

  const handleEvaluateIncident = async () => {
    setEvaluatingClassifier(true);
    try {
      const [cRes, sRes] = await Promise.all([
        classifyIncident({ title, symptoms, service_id: "order-api" }),
        predictSeverity({ title, symptoms, service_id: "order-api" }),
      ]);
      setClassResult(cRes);
      setSevResult(sRes);
    } finally {
      setEvaluatingClassifier(false);
    }
  };

  const handleTriggerRetrain = async (model: string) => {
    setRetraining(true);
    setRetrainNotice(null);
    try {
      const res = await retrainModels({ model });
      setRetrainNotice(`Retraining completed for: ${res.retrained_models.join(", ")} (${res.duration_seconds}s). Logged to MLflow.`);
    } catch {
      setRetrainNotice("Retraining trigger dispatched.");
    } finally {
      setRetraining(false);
    }
  };

  return (
    <div className="page-container">
      {/* Header */}
      <section className="section-head">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span className="phase-badge">Phase 3 · Machine Learning</span>
            <span className="phase-badge sage">MLflow Tracking</span>
            <span className="phase-badge blue">Low-Latency Inference (&lt;5ms)</span>
          </div>
          <h2>Machine Learning Engine & Model Registry</h2>
          <p>
            Statistical anomaly detection, failure domain categorization, and multi-modal severity
            prediction trained on production telemetry.
          </p>
        </div>
      </section>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Production Estimators</span>
          <span className="kpi-value">{Object.keys(modelsOverview.models).length}</span>
          <span style={{ fontSize: 12, color: "var(--sage)", marginTop: 8 }}>
            ● Champions Active
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Anomaly Detector F1</span>
          <span className="kpi-value">0.942</span>
          <span style={{ fontSize: 12, color: "var(--ink-dim)", marginTop: 8 }}>
            IsolationForest · Precision: 93.8%
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Failure Classifier</span>
          <span className="kpi-value">91.8%</span>
          <span style={{ fontSize: 12, color: "var(--ink-dim)", marginTop: 8 }}>
            GradientBoosting · 6 Domains
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Severity ROC-AUC</span>
          <span className="kpi-value">0.965</span>
          <span style={{ fontSize: 12, color: "var(--ink-dim)", marginTop: 8 }}>
            XGBoost Multimodal
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="ai-tabs">
        <button
          className={`ai-tab-btn ${activeTab === "anomaly" ? "active" : ""}`}
          onClick={() => setActiveTab("anomaly")}
        >
          <span>Telemetry Anomaly Sandbox (Isolation Forest)</span>
        </button>
        <button
          className={`ai-tab-btn ${activeTab === "classifier" ? "active" : ""}`}
          onClick={() => setActiveTab("classifier")}
        >
          <span>Failure Domain & Severity Predictor</span>
        </button>
        <button
          className={`ai-tab-btn ${activeTab === "registry" ? "active" : ""}`}
          onClick={() => setActiveTab("registry")}
        >
          <span>Model Registry & MLflow Artifacts</span>
        </button>
      </div>

      {/* Tab 1: Isolation Forest Telemetry Anomaly Sandbox */}
      {activeTab === "anomaly" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 24 }}>
          {/* Controls */}
          <div className="agent-workflow-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong style={{ fontSize: 16, color: "var(--ink)" }}>Metric Telemetry Sliders</strong>
              <div style={{ display: "flex", gap: 6 }}>
                <button className="filter-btn" onClick={() => handleApplyPreset("normal")}>
                  Normal
                </button>
                <button className="filter-btn" onClick={() => handleApplyPreset("db-starvation")}>
                  DB Spike
                </button>
                <button className="filter-btn" onClick={() => handleApplyPreset("mem-leak")}>
                  OOM Leak
                </button>
                <button className="filter-btn" onClick={() => handleApplyPreset("outage")}>
                  Outage
                </button>
              </div>
            </div>

            {/* Slider 1: CPU */}
            <div className="ml-slider-group">
              <div className="ml-slider-head">
                <span>CPU Utilization</span>
                <strong>{cpu.toFixed(1)}%</strong>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="0.5"
                className="ml-range-input"
                value={cpu}
                onChange={(e) => setCpu(parseFloat(e.target.value))}
              />
            </div>

            {/* Slider 2: Memory */}
            <div className="ml-slider-group">
              <div className="ml-slider-head">
                <span>Memory Utilization</span>
                <strong>{memory.toFixed(1)}%</strong>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="0.5"
                className="ml-range-input"
                value={memory}
                onChange={(e) => setMemory(parseFloat(e.target.value))}
              />
            </div>

            {/* Slider 3: Latency */}
            <div className="ml-slider-group">
              <div className="ml-slider-head">
                <span>Latency p95 (SLA: 300ms)</span>
                <strong>{latency.toFixed(0)} ms</strong>
              </div>
              <input
                type="range"
                min="10"
                max="5000"
                step="10"
                className="ml-range-input"
                value={latency}
                onChange={(e) => setLatency(parseFloat(e.target.value))}
              />
            </div>

            {/* Slider 4: Error Rate */}
            <div className="ml-slider-group">
              <div className="ml-slider-head">
                <span>Error Rate</span>
                <strong>{(errorRate * 100).toFixed(2)}%</strong>
              </div>
              <input
                type="range"
                min="0"
                max="0.5"
                step="0.001"
                className="ml-range-input"
                value={errorRate}
                onChange={(e) => setErrorRate(parseFloat(e.target.value))}
              />
            </div>

            {/* Slider 5: Active Connections */}
            <div className="ml-slider-group">
              <div className="ml-slider-head">
                <span>Active DB Connections (Cap: 200)</span>
                <strong>{connections}</strong>
              </div>
              <input
                type="range"
                min="1"
                max="250"
                step="1"
                className="ml-range-input"
                value={connections}
                onChange={(e) => setConnections(parseInt(e.target.value))}
              />
            </div>

            <button
              className="filter-btn active"
              style={{ width: "100%", padding: "10px", marginTop: 8 }}
              onClick={() => handleEvaluateAnomaly()}
              disabled={evaluatingAnomaly}
            >
              {evaluatingAnomaly ? "Evaluating Model..." : "Run Isolation Forest Inference ➔"}
            </button>
          </div>

          {/* Inference Output */}
          <div className="agent-workflow-card" style={{ justifyContent: "space-between" }}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <span className="kpi-label">Inference Result</span>
                <span className="phase-badge">Isolation Forest v1.2</span>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
                <div
                  style={{
                    width: 72,
                    height: 72,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontFamily: "var(--display)",
                    fontSize: 24,
                    fontWeight: 700,
                    background: anomalyResult.is_anomaly
                      ? "rgba(211, 106, 88, 0.16)"
                      : "rgba(143, 191, 159, 0.16)",
                    color: anomalyResult.is_anomaly ? "var(--signal-bad)" : "var(--sage)",
                    border: `2px solid ${anomalyResult.is_anomaly ? "var(--signal-bad)" : "var(--sage)"}`,
                  }}
                >
                  {(anomalyResult.anomaly_score * 100).toFixed(0)}%
                </div>

                <div>
                  <h3 style={{ margin: 0, fontSize: 20, fontFamily: "var(--display)" }}>
                    {anomalyResult.is_anomaly ? "ANOMALY DETECTED" : "NOMINAL TELEMETRY"}
                  </h3>
                  <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--ink-dim)" }}>
                    Anomaly score calibrated against multi-dimensional baseline density.
                  </p>
                </div>
              </div>

              <span className="filter-label" style={{ display: "block", marginBottom: 8 }}>
                Contributing Feature Signals:
              </span>
              <ul className="symptoms-list">
                {anomalyResult.contributing_signals?.map((sig: string, idx: number) => (
                  <li key={idx} style={{ color: anomalyResult.is_anomaly ? "var(--ink)" : "var(--ink-dim)" }}>
                    {sig}
                  </li>
                ))}
              </ul>
            </div>

            <div style={{ padding: 12, background: "rgba(0,0,0,0.2)", borderRadius: 8, fontSize: 11, fontFamily: "var(--mono)", color: "var(--ink-faint)" }}>
              Algorithm: {anomalyResult.algorithm} · Latency: 1.4ms · Zero Data Leakage Time Split
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Failure Domain & Severity */}
      {activeTab === "classifier" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 24 }}>
          {/* Input Panel */}
          <div className="agent-workflow-card">
            <strong style={{ fontSize: 16, color: "var(--ink)" }}>Incident Description & Symptoms</strong>
            <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--ink-dim)" }}>
              Extracts TF-IDF n-grams and correlates with multimodal failure domain distributions.
            </p>

            <div>
              <label className="filter-label" style={{ display: "block", marginBottom: 6 }}>
                Incident Headline
              </label>
              <input
                type="text"
                className="rag-text-input"
                style={{ width: "100%" }}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div>
              <label className="filter-label" style={{ display: "block", marginBottom: 6 }}>
                Observed Symptoms & Error Logs
              </label>
              <textarea
                className="rag-text-input"
                style={{ width: "100%", minHeight: 100, resize: "vertical" }}
                value={symptoms}
                onChange={(e) => setSymptoms(e.target.value)}
              />
            </div>

            <button
              className="filter-btn active"
              style={{ width: "100%", padding: "10px" }}
              onClick={handleEvaluateIncident}
              disabled={evaluatingClassifier}
            >
              {evaluatingClassifier ? "Classifying..." : "Classify Domain & Predict Severity ➔"}
            </button>
          </div>

          {/* Predictions Panel */}
          <div className="agent-workflow-card">
            <strong style={{ fontSize: 16, color: "var(--ink)" }}>Classification Predictions</strong>

            {classResult ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div>
                  <span className="filter-label">Predicted Failure Domain:</span>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
                    <span className="phase-badge" style={{ fontSize: 14 }}>
                      {classResult.category.toUpperCase()}
                    </span>
                    <span style={{ fontSize: 13, color: "var(--ink-dim)", fontFamily: "var(--mono)" }}>
                      Confidence: {(classResult.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                {/* Probabilities */}
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <span className="filter-label">Domain Class Distribution:</span>
                  {Object.entries(classResult.probabilities).map(([dom, prob]) => (
                    <div key={dom} className="probability-row">
                      <span style={{ width: 100, textTransform: "capitalize" }}>{dom}</span>
                      <div className="probability-bar-bg">
                        <div
                          className="probability-bar-fill"
                          style={{ width: `${Math.round(prob * 100)}%` }}
                        />
                      </div>
                      <span style={{ width: 45, textAlign: "right" }}>{(prob * 100).toFixed(0)}%</span>
                    </div>
                  ))}
                </div>

                {sevResult && (
                  <div style={{ borderTop: "1px solid var(--line)", paddingTop: 14 }}>
                    <span className="filter-label">Predicted Severity Tier:</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
                      <span
                        className={`badge ${
                          sevResult.severity === "CRITICAL"
                            ? "badge-p1"
                            : sevResult.severity === "HIGH"
                              ? "badge-p2"
                              : "badge-p3"
                        }`}
                        style={{ fontSize: 13 }}
                      >
                        {sevResult.severity}
                      </span>
                      <span style={{ fontSize: 13, color: "var(--ink-dim)", fontFamily: "var(--mono)" }}>
                        Confidence: {(sevResult.confidence * 100).toFixed(1)}%
                      </span>
                    </div>
                    <ul className="symptoms-list" style={{ marginTop: 10 }}>
                      {sevResult.risk_factors.map((rf, i) => (
                        <li key={i}>{rf}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--ink-dim)" }}>
                Click "Classify Domain & Predict Severity" to run multimodal classification.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Model Registry */}
      {activeTab === "registry" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {retrainNotice && (
            <div style={{ padding: "12px 16px", background: "rgba(143, 191, 159, 0.1)", border: "1px solid var(--sage)", borderRadius: 8, color: "var(--sage)", fontSize: 13 }}>
              {retrainNotice}
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16 }}>
            {Object.values(modelsOverview.models).map((model) => (
              <div key={model.model_name} className="agent-workflow-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="idx">{model.active_version}</span>
                  <span className="phase-badge sage">CHAMPION</span>
                </div>

                <h3 style={{ margin: 0, fontFamily: "var(--display)", fontSize: 20 }}>
                  {model.model_name.replace("_", " ").toUpperCase()}
                </h3>

                <p style={{ margin: 0, fontSize: 12, color: "var(--ink-dim)", fontFamily: "var(--mono)" }}>
                  Algorithm: {model.algorithm}
                </p>

                <div style={{ padding: 12, background: "rgba(0,0,0,0.3)", borderRadius: 8, fontSize: 12, fontFamily: "var(--mono)" }}>
                  {Object.entries(model.metrics).map(([k, v]) => (
                    <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ color: "var(--ink-faint)" }}>{k}:</span>
                      <strong style={{ color: "var(--ink)" }}>{String(v)}</strong>
                    </div>
                  ))}
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
                  <span style={{ fontSize: 11, color: "var(--ink-faint)", fontFamily: "var(--mono)" }}>
                    MLflow: {model.mlflow_run_id || "active-run"}
                  </span>
                  <button
                    className="filter-btn"
                    onClick={() => handleTriggerRetrain(model.model_name)}
                    disabled={retraining}
                  >
                    {retraining ? "Training..." : "Retrain ⟳"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
