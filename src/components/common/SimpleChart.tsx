import type { CSSProperties } from "react";

export interface DataPoint {
  label: string;
  value: number;
  secondaryValue?: number;
}

interface SparklineProps {
  data: number[];
  width?: number | string;
  height?: number;
  color?: string;
  fill?: boolean;
  style?: CSSProperties;
}

export function Sparkline({
  data,
  width = "100%",
  height = 48,
  color = "var(--filament, #d4784a)",
  fill = true,
  style,
}: SparklineProps) {
  if (!data || data.length === 0) {
    return <div style={{ height, width, background: "rgba(255,255,255,0.02)", borderRadius: 6 }} />;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const w = 100;
  const h = height;
  const padding = 4;

  const points = data.map((val, idx) => {
    const x = padding + (idx / Math.max(data.length - 1, 1)) * (w - padding * 2);
    const y = h - padding - ((val - min) / range) * (h - padding * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const pathD = `M ${points.join(" L ")}`;
  const areaD = `${pathD} L ${w - padding},${h} L ${padding},${h} Z`;

  const gradientId = `spark-grad-${Math.random().toString(36).substring(2, 8)}`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      style={{ width, height, overflow: "visible", ...style }}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0.0" />
        </linearGradient>
      </defs>
      {fill && <path d={areaD} fill={`url(#${gradientId})`} />}
      <path d={pathD} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

interface DistributionSegment {
  label: string;
  count: number;
  color: string;
}

interface DistributionBarProps {
  segments: DistributionSegment[];
  total?: number;
  height?: number;
  showLabels?: boolean;
}

export function DistributionBar({
  segments,
  total: explicitTotal,
  height = 10,
  showLabels = true,
}: DistributionBarProps) {
  const calculatedTotal = segments.reduce((sum, s) => sum + s.count, 0);
  const total = explicitTotal ?? (calculatedTotal || 1);

  return (
    <div style={{ width: "100%" }}>
      <div
        style={{
          display: "flex",
          height: `${height}px`,
          width: "100%",
          borderRadius: "999px",
          overflow: "hidden",
          backgroundColor: "rgba(255,255,255,0.06)",
        }}
      >
        {segments.map((seg, idx) => {
          const pct = Math.max((seg.count / total) * 100, 0);
          if (pct === 0) return null;
          return (
            <div
              key={idx}
              title={`${seg.label}: ${seg.count} (${pct.toFixed(1)}%)`}
              style={{
                width: `${pct}%`,
                backgroundColor: seg.color,
                transition: "width 0.3s ease",
              }}
            />
          );
        })}
      </div>
      {showLabels && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "12px",
            marginTop: "8px",
            fontSize: "12px",
            fontFamily: "var(--mono, monospace)",
          }}
        >
          {segments.map((seg, idx) => (
            <span key={idx} style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: seg.color }} />
              <span style={{ color: "var(--ink-dim, #b7aaa0)" }}>{seg.label}:</span>
              <strong style={{ color: "var(--ink, #f3ece4)" }}>{seg.count}</strong>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

interface TimeSeriesChartProps {
  series?: {
    name: string;
    data: number[];
    color: string;
  }[];
  labels?: string[];
  data?: number[];
  timestamps?: string[];
  color?: string;
  height?: number;
  threshold?: { value: number; label: string; color?: string };
  unit?: string;
}

export function TimeSeriesChart({
  series,
  labels,
  data,
  timestamps,
  color = "var(--filament, #d4784a)",
  height = 200,
  threshold,
  unit = "",
}: TimeSeriesChartProps) {
  const chartSeries =
    series || (data && data.length > 0 ? [{ name: "Value", data, color }] : []);
  const chartLabels =
    labels ||
    timestamps ||
    (chartSeries.length > 0 && chartSeries[0].data ? chartSeries[0].data.map((_, i) => `${i}`) : []);

  if (
    !chartSeries.length ||
    !chartLabels.length ||
    !chartSeries.some((s) => s.data && s.data.length > 0)
  ) {
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--ink-faint)",
        }}
      >
        No telemetry data available
      </div>
    );
  }

  const allVals = chartSeries.flatMap((s) => s.data || []);
  if (threshold) allVals.push(threshold.value);

  const min = Math.min(...allVals, 0);
  const max = Math.max(...allVals, 10);
  const range = max - min || 1;

  const w = 500;
  const h = height;
  const padLeft = 40;
  const padRight = 10;
  const padTop = 15;
  const padBottom = 25;

  const innerW = w - padLeft - padRight;
  const innerH = h - padTop - padBottom;

  const getY = (v: number) => padTop + innerH - ((v - min) / range) * innerH;

  return (
    <div style={{ width: "100%", overflowX: "auto" }}>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        style={{ width: "100%", minWidth: "360px", height, overflow: "visible" }}
      >
        {/* Horizontal grid lines */}
        {[0, 0.25, 0.5, 0.75, 1.0].map((frac, idx) => {
          const val = min + frac * range;
          const y = getY(val);
          return (
            <g key={idx}>
              <line
                x1={padLeft}
                y1={y}
                x2={w - padRight}
                y2={y}
                stroke="var(--line, rgba(255,255,255,0.06))"
                strokeDasharray="2,2"
              />
              <text
                x={padLeft - 6}
                y={y + 3}
                fill="var(--ink-faint, #8a7d73)"
                fontSize="10"
                fontFamily="var(--mono, monospace)"
                textAnchor="end"
              >
                {Math.round(val)}
                {unit}
              </text>
            </g>
          );
        })}

        {/* Threshold line if defined */}
        {threshold && (
          <g>
            <line
              x1={padLeft}
              y1={getY(threshold.value)}
              x2={w - padRight}
              y2={getY(threshold.value)}
              stroke={threshold.color || "#ff6b6b"}
              strokeWidth="1.2"
              strokeDasharray="4,3"
            />
            <text
              x={w - padRight}
              y={getY(threshold.value) - 4}
              fill={threshold.color || "#ff6b6b"}
              fontSize="10"
              fontFamily="var(--mono, monospace)"
              textAnchor="end"
            >
              {threshold.label} ({threshold.value}{unit})
            </text>
          </g>
        )}

        {/* Series paths */}
        {chartSeries.map((s, sIdx) => {
          const pts = (s.data || []).map((val, idx) => {
            const x = padLeft + (idx / Math.max(chartLabels.length - 1, 1)) * innerW;
            const y = getY(val);
            return `${x.toFixed(1)},${y.toFixed(1)}`;
          });
          const pathD = `M ${pts.join(" L ")}`;

          return (
            <path
              key={sIdx}
              d={pathD}
              fill="none"
              stroke={s.color}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          );
        })}

        {/* X-axis labels */}
        {chartLabels.map((lbl, idx) => {
          if (idx % Math.ceil(chartLabels.length / 5) !== 0 && idx !== chartLabels.length - 1) return null;
          const x = padLeft + (idx / Math.max(chartLabels.length - 1, 1)) * innerW;
          return (
            <text
              key={idx}
              x={x}
              y={h - 6}
              fill="var(--ink-faint, #8a7d73)"
              fontSize="10"
              fontFamily="var(--mono, monospace)"
              textAnchor="middle"
            >
              {lbl}
            </text>
          );
        })}
      </svg>
      {/* Legend */}
      <div style={{ display: "flex", gap: "16px", marginTop: "8px", fontSize: "11px", fontFamily: "var(--mono, monospace)" }}>
        {chartSeries.map((s, idx) => (
          <span key={idx} style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
            <span style={{ width: 12, height: 3, backgroundColor: s.color, borderRadius: 2 }} />
            <span style={{ color: "var(--ink-dim)" }}>{s.name}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
