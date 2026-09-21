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
  const [selectedService, setSelectedService] = useState<string>("checkout-service");
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [summary, setSummary] = useState<MetricSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadServices() {
      const svcs = await fetchServices();
      setServices(svcs);
      if (svcs.length > 0 && !svcs.find((s) => s.id === selectedService)) {
        setSelectedService(svcs[0].id);
      }
    }
    loadServices();
  }, [selectedService]);

  useEffect(() => {
    async function loadTelemetry() {
      if (!selectedService) return;
      setLoading(true);
      const [mList, mSummary] = await Promise.all([
        fetchMetrics(selectedService, 30),
        fetchMetricsSummary(selectedService),
      ]);
      // Sort chronologically ascending for charts
      const sorted = [...mList].sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
      );
      setMetrics(sorted);
      setSummary(mSummary);
      setLoading(false);
    }
    loadTelemetry();
  }, [selectedService]);

  // Helper to render responsive SVG area/line chart
  const renderSvgChart = (
    data: number[],
    color: string,
    _unit: string,
    minVal: number = 0,
    maxVal?: number,
  ) => {
    if (data.length < 2) return null;
    const computedMax = maxVal ?? Math.max(...data, 1);
    const range = computedMax - minVal || 1;
    const width = 500;
    const height = 120;
    const padding = 10;

    const points = data.map((val, idx) => {
      const x = padding + (idx / (data.length - 1)) * (width - padding * 2);
      const normalized = (val - minVal) / range;
      const y = height - padding - normalized * (height - padding * 2);
      return { x, y };
    });

    const pathD = points.reduce(
      (acc, pt, idx) => `${acc} ${idx === 0 ? "M" : "L"} ${pt.x},${pt.y}`,
      "",
    );

    const areaD = `${pathD} L ${points[points.length - 1].x},${height - padding} L ${points[0].x},${height - padding} Z`;

    return (
      <div className="chart-svg-container">
        <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" preserveAspectRatio="none">
          <defs>
            <linearGradient id={`grad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
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
          <path d={areaD} fill={`url(#grad-${color.replace("#", "")})`} />

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
            {currentMetric ? `${currentMetric.cpu_utilization.toFixed(1)}%` : "..."}
          </span>
          <span className="kpi-sub">
            Avg: {summary?.avg_cpu ?? "-"}% · Peak: {summary?.max_cpu ?? "-"}%
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Memory Utilization</span>
          <span className="kpi-value">
            {currentMetric ? `${currentMetric.memory_utilization.toFixed(1)}%` : "..."}
          </span>
          <span className="kpi-sub">
            Avg: {summary?.avg_memory ?? "-"}% · Peak: {summary?.max_memory ?? "-"}%
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">p95 Request Latency</span>
          <span
            className="kpi-value"
            style={{
              color:
                currentMetric && currentMetric.request_latency_p95 > 1000
                  ? "var(--signal-bad)"
                  : "inherit",
            }}
          >
            {currentMetric ? `${Math.round(currentMetric.request_latency_p95)}ms` : "..."}
          </span>
          <span className="kpi-sub">
            Avg: {summary ? Math.round(summary.avg_latency_p95) : "-"}ms · Peak:{" "}
            {summary ? Math.round(summary.max_latency_p95) : "-"}ms
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">HTTP Error Rate</span>
          <span
            className="kpi-value"
            style={{
              color:
                currentMetric && currentMetric.error_rate > 2
                  ? "var(--signal-bad)"
                  : "inherit",
            }}
          >
            {currentMetric ? `${currentMetric.error_rate.toFixed(2)}%` : "..."}
          </span>
          <span className="kpi-sub">
            Avg: {summary?.avg_error_rate ?? "-"}% · Max: {summary?.max_error_rate ?? "-"}%
          </span>
        </div>
      </section>

      {/* Charts Grid */}
      <section>
        <div className="section-head">
          <div>
            <h2>Telemetry Trends (Last 25 Interval Windows)</h2>
            <p>Fine-grained resource utilization and SLA time-series.</p>
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
                  {currentMetric ? `${currentMetric.cpu_utilization.toFixed(1)}%` : ""}
                </span>
              </div>
              {renderSvgChart(
                metrics.map((m) => m.cpu_utilization),
                "#d4784a",
                "%",
                0,
                100,
              )}
            </div>

            {/* Chart 2: Memory */}
            <div className="chart-card">
              <div className="chart-header">
                <span className="chart-title">Memory Allocation (%)</span>
                <span className="chart-cur-val">
                  {currentMetric ? `${currentMetric.memory_utilization.toFixed(1)}%` : ""}
                </span>
              </div>
              {renderSvgChart(
                metrics.map((m) => m.memory_utilization),
                "#8fbf9f",
                "%",
                0,
                100,
              )}
            </div>

            {/* Chart 3: Latency */}
            <div className="chart-card">
              <div className="chart-header">
                <span className="chart-title">p95 Request Latency (ms)</span>
                <span className="chart-cur-val">
                  {currentMetric ? `${Math.round(currentMetric.request_latency_p95)} ms` : ""}
                </span>
              </div>
              {renderSvgChart(
                metrics.map((m) => m.request_latency_p95),
                currentMetric && currentMetric.request_latency_p95 > 1000 ? "#d36a58" : "#d4784a",
                "ms",
                0,
              )}
            </div>

            {/* Chart 4: Error Rate */}
            <div className="chart-card">
              <div className="chart-header">
                <span className="chart-title">Error Rate (%)</span>
                <span className="chart-cur-val">
                  {currentMetric ? `${currentMetric.error_rate.toFixed(2)}%` : ""}
                </span>
              </div>
              {renderSvgChart(
                metrics.map((m) => m.error_rate),
                "#d36a58",
                "%",
                0,
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
