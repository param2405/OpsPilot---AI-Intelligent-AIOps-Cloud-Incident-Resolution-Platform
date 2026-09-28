import type { CSSProperties, ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  unit?: string;
  sublabel?: string;
  trend?: {
    value: string | number;
    isPositive?: boolean;
    isNeutral?: boolean;
  };
  icon?: ReactNode;
  alert?: boolean;
  style?: CSSProperties;
  className?: string;
}

export function MetricCard({
  label,
  value,
  unit,
  sublabel,
  trend,
  icon,
  alert = false,
  style,
  className = "",
}: MetricCardProps) {
  return (
    <div
      className={`metric-stat-card ${alert ? "metric-alert" : ""} ${className}`}
      style={{
        borderRadius: "var(--radius, 14px)",
        border: alert
          ? "1px solid rgba(224, 76, 76, 0.4)"
          : "1px solid var(--line, rgba(255,255,255,0.1))",
        background: alert
          ? "linear-gradient(180deg, rgba(224, 76, 76, 0.08), rgba(224, 76, 76, 0.02)), var(--bg-panel, #211c17)"
          : "linear-gradient(180deg, rgba(255, 255, 255, 0.03), transparent 80%), var(--bg-panel, #211c17)",
        padding: "18px 20px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        boxShadow: "0 4px 20px rgba(0,0,0,0.18)",
        position: "relative",
        overflow: "hidden",
        ...style,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
        <span
          style={{
            fontSize: "12px",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: alert ? "#ff6b6b" : "var(--ink-dim, #b7aaa0)",
          }}
        >
          {label}
        </span>
        {icon && <span style={{ opacity: 0.8, color: alert ? "#ff6b6b" : "var(--filament, #d4784a)" }}>{icon}</span>}
      </div>

      <div style={{ display: "flex", alignItems: "baseline", gap: "6px", margin: "6px 0 2px" }}>
        <span
          style={{
            fontSize: "28px",
            fontWeight: 700,
            fontFamily: "var(--mono, monospace)",
            color: alert ? "#ff6b6b" : "var(--ink, #f3ece4)",
            lineHeight: 1.1,
          }}
        >
          {value}
        </span>
        {unit && (
          <span
            style={{
              fontSize: "14px",
              fontFamily: "var(--mono, monospace)",
              color: "var(--ink-faint, #8a7d73)",
              fontWeight: 500,
            }}
          >
            {unit}
          </span>
        )}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "8px", fontSize: "12px" }}>
        {sublabel && (
          <span style={{ color: "var(--ink-faint, #8a7d73)" }}>
            {sublabel}
          </span>
        )}
        {trend && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              fontWeight: 600,
              fontFamily: "var(--mono, monospace)",
              fontSize: "11px",
              color: trend.isNeutral
                ? "var(--ink-dim, #b7aaa0)"
                : trend.isPositive
                ? "var(--sage, #8fbf9f)"
                : "var(--signal-bad, #d36a58)",
            }}
          >
            {trend.value}
          </span>
        )}
      </div>
    </div>
  );
}
