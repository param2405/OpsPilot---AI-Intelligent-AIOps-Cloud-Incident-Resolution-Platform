import { useEffect, useState } from "react";
import {
  fetchMetrics,
  fetchMetricsSummary,
  fetchServices,
  Metric,
  MetricSummary,
  Service,
} from "../api/observability";

export function MetricsPage() {
  const [services, setServices] = useState<Service[]>([]);
  const [selectedService, setSelectedService] = useState<string>("");
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [summary, setSummary] = useState<MetricSummary | null>(null);
  const [loading, setLoading] = useState(true);

  // 1. Initial service list fetch
  useEffect(() => {
    let isMounted = true;
    async function loadServices() {
      const svcs = await fetchServices();
      if (!isMounted) return;
      setServices(svcs);
      if (svcs.length > 0) {
        setSelectedService((prev) => (prev ? prev : svcs[0].id));
      }
    }
    loadServices();
    return () => {
      isMounted = false;
    };
  }, []);

  // 2. Fetch telemetry when selected service changes
  useEffect(() => {
    let isMounted = true;
    if (!selectedService) return;

    async function loadTelemetry() {
      setLoading(true);
      try {
        const [mList, mSummary] = await Promise.all([
          fetchMetrics(selectedService, 30),
          fetchMetricsSummary(selectedService),
        ]);
        if (!isMounted) return;

        const sorted = [...mList].sort(
          (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
        );
        setMetrics(sorted);
        setSummary(mSummary);
      } catch (err) {
        console.error("Failed to load telemetry:", err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadTelemetry();
    return () => {
      isMounted = false;
    };
  }, [selectedService]);

  // Defensive SVG chart renderer
  const renderSvgChart = (
    data: number[],
    color: string,
    minVal: number = 0,
    maxVal?: number,
  ) => {
    const validData = (data || []).map((v) => (Number.isFinite(v) ? Number(v) : 0));
    if (validData.length < 2) {
      return (
        <div style={{ padding: "30px", textAlign: "center", color: "var(--ink-faint)", fontSize: "12px" }}>
          Gathering telemetry time-series points...
        </div>
      );
    }

    const computedMax = maxVal ?? Math.max(...validData, 1);
    const range = Math.max(computedMax - minVal, 1);
    const width = 500;
    const height = 120;
    const padding = 12;

    const points = validData.map((val, idx) => {
      const x = padding + (idx / (validData.length - 1)) * (width - padding * 2);
      const normalized = Math.min(Math.max((val - minVal) / range, 0), 1);
      const y = height - padding - normalized * (height - padding * 2);
      return { x, y };
    });

    const pathD = points.reduce(
      (acc, pt, idx) => `${acc} ${idx === 0 ? "M" : "L"} ${pt.x},${pt.y}`,
      "",
    );

    const areaD = `${pathD} L ${points[points.length - 1].x},${height - padding} L ${points[0].x},${height - padding} Z`;

    const gradId = `grad-${color.replace(/[^a-zA-Z0-9]/g, "")}`;

    return (
      <div className="chart-svg-container">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" preserveAspectRatio="none">
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.35" />
              <stop offset="100%" stopColor={color} stopOpacity="0.0" />
            </linearGradient>
          </defs>
          {/* Subtle gridlines */}
          <line
            x1={padding}
            y1={height - padding}
            x2={width - padding}
            y2={height - padding}
            stroke="var(--line)"
            strokeWidth="1"
          />
          <line
            x1={padding}
            y1={height / 2}
            x2={width - padding}
            y2={height / 2}
            stroke="var(--line)"
            strokeDasharray="4 4"
            strokeWidth="1"
          />

          {/* Shaded Area */}
          <path d={areaD} fill={`url(#${gradId})`} />

          {/* Telemetry Line */}
          <path d={pathD} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" />

          {/* Latest Point Indicator */}
          {points.length > 0 && (
            <circle
              cx={points[points.length - 1].x}
              cy={points[points.length - 1].y}
              r="4"
              fill={color}
              stroke="var(--bg-panel)"
              strokeWidth="2"
            />
          )}
        </svg>
      </div>
    );
  };

  const currentMetric = metrics.length > 0 ? metrics[metrics.length - 1] : null;
  const cpuVal = currentMetric?.cpu_usage ?? 0;
  const memVal = currentMetric?.memory_usage ?? 0;
  const latVal = currentMetric?.latency_p95_ms ?? 0;
  const errVal = currentMetric?.error_rate ?? 0;
  // If error rate is fractional (e.g. 0.04), convert to percentage
  const errPct = errVal < 1 ? errVal * 100 : errVal;

  return (
    <div className="page-container">
      {/* Top Controls */}
      <section className="filter-bar" style={{ justifyContent: "space-between" }}>
        <div className="filter-group">
          <span className="filter-label">Selected Node:</span>
          <select
            className="select-input"
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
          >
            {services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.id})
              </option>
            ))}
          </select>
        </div>

        <div className="pill">
          <span className="dot ok" />
          <span>High-Frequency Telemetry Ingestion Active</span>
        </div>
      </section>

      {/* Aggregate KPI Summary Cards */}
      <section className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">CPU Utilization</span>
          <span className="kpi-value">
            {currentMetric ? `${cpuVal.toFixed(1)}%` : "..."}
          </span>
          <span className="kpi-sub">
            Avg: {summary?.avg_cpu_usage?.toFixed(1) ?? "-"}% · Peak: {summary?.max_cpu_usage?.toFixed(1) ?? "-"}%
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Memory Utilization</span>
          <span className="kpi-value">
            {currentMetric ? `${memVal.toFixed(1)}%` : "..."}
          </span>
          <span className="kpi-sub">
            Avg: {summary?.avg_memory_usage?.toFixed(1) ?? "-"}% · Peak: {summary?.max_memory_usage?.toFixed(1) ?? "-"}%
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">p95 Request Latency</span>
          <span
            className="kpi-value"
            style={{
              color: latVal > 1000 ? "var(--signal-bad)" : "inherit",
            }}
          >
            {currentMetric ? `${Math.round(latVal)}ms` : "..."}
          </span>
          <span className="kpi-sub">
            Avg: {summary ? Math.round(summary.avg_latency_p95_ms) : "-"}ms · Peak:{" "}
            {summary ? Math.round(summary.max_latency_p95_ms) : "-"}ms
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">HTTP Error Rate</span>
          <span
            className="kpi-value"
            style={{
              color: errPct > 2 ? "var(--signal-bad)" : "inherit",
            }}
          >
            {currentMetric ? `${errPct.toFixed(2)}%` : "..."}
          </span>
          <span className="kpi-sub">
            Avg: {summary ? `${(summary.avg_error_rate * (summary.avg_error_rate < 1 ? 100 : 1)).toFixed(2)}%` : "-"}
          </span>
        </div>
      </section>

      {/* Charts Grid */}
      <section>
        <div className="section-head">
          <div>
            <h2>Telemetry Trends ({metrics.length} Recorded Windows)</h2>
            <p>Fine-grained resource utilization and SLA time-series for {selectedService}.</p>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: "40px", textAlign: "center", color: "var(--ink-dim)" }}>
            Loading telemetry streams...
          </div>
        ) : (
          <div className="charts-grid">
            {/* Chart 1: CPU */}
            <div className="chart-card">
              <div className="chart-header">
                <span className="chart-title">CPU Utilization (%)</span>
                <span className="chart-cur-val">
                  {currentMetric ? `${cpuVal.toFixed(1)}%` : ""}
                </span>
              </div>
              {renderSvgChart(
                metrics.map((m) => m.cpu_usage),
                "#d4784a",
                0,
                100,
              )}
            </div>

            {/* Chart 2: Memory */}
            <div className="chart-card">
              <div className="chart-header">
                <span className="chart-title">Memory Allocation (%)</span>
                <span className="chart-cur-val">
                  {currentMetric ? `${memVal.toFixed(1)}%` : ""}
                </span>
              </div>
              {renderSvgChart(
                metrics.map((m) => m.memory_usage),
                "#8fbf9f",
                0,
                100,
              )}
            </div>

            {/* Chart 3: Latency */}
            <div className="chart-card">
              <div className="chart-header">
                <span className="chart-title">p95 Request Latency (ms)</span>
                <span className="chart-cur-val">
                  {currentMetric ? `${Math.round(latVal)} ms` : ""}
                </span>
              </div>
              {renderSvgChart(
                metrics.map((m) => m.latency_p95_ms),
                latVal > 1000 ? "#d36a58" : "#d4784a",
                0,
              )}
            </div>

            {/* Chart 4: Error Rate */}
            <div className="chart-card">
              <div className="chart-header">
                <span className="chart-title">Error Rate (%)</span>
                <span className="chart-cur-val">
                  {currentMetric ? `${errPct.toFixed(2)}%` : ""}
                </span>
              </div>
              {renderSvgChart(
                metrics.map((m) => (m.error_rate < 1 ? m.error_rate * 100 : m.error_rate)),
                "#d36a58",
                0,
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
