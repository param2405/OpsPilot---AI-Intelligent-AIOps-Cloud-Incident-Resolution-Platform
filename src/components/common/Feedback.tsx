import type { CSSProperties, ReactNode } from "react";

export function LoadingSpinner({
  size = 24,
  label,
  message,
  style,
}: {
  size?: number;
  label?: string;
  message?: string;
  style?: CSSProperties;
}) {
  const display = label || message || "Loading telemetry...";
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "12px",
        padding: "32px",
        color: "var(--ink-dim, #b7aaa0)",
        ...style,
      }}
    >
      <div
        style={{
          width: `${size}px`,
          height: `${size}px`,
          border: "2px solid rgba(212, 120, 74, 0.2)",
          borderTopColor: "var(--filament, #d4784a)",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
        }}
      />
      {display && <span style={{ fontSize: "13px", fontFamily: "var(--mono, monospace)" }}>{display}</span>}
    </div>
  );
}

export function Skeleton({
  height = 20,
  width = "100%",
  borderRadius = 6,
  style,
}: {
  height?: number | string;
  width?: number | string;
  borderRadius?: number;
  style?: CSSProperties;
}) {
  return (
    <div
      className="skeleton"
      style={{
        height,
        width,
        borderRadius,
        backgroundColor: "rgba(255, 255, 255, 0.05)",
        backgroundImage: "linear-gradient(90deg, rgba(255,255,255,0) 0, rgba(255,255,255,0.06) 50%, rgba(255,255,255,0) 100%)",
        backgroundSize: "200% 100%",
        animation: "skeletonShimmer 1.5s infinite",
        ...style,
      }}
    />
  );
}

export function EmptyState({
  title = "No records found",
  message = "No operational events match the current filter criteria.",
  icon,
  action,
  style,
}: {
  title?: string;
  message?: string;
  icon?: ReactNode;
  action?: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "48px 24px",
        textAlign: "center",
        borderRadius: "var(--radius, 14px)",
        border: "1px dashed var(--line, rgba(255,255,255,0.1))",
        backgroundColor: "rgba(255, 255, 255, 0.01)",
        ...style,
      }}
    >
      <div style={{ fontSize: "32px", marginBottom: "12px", opacity: 0.6, color: "var(--filament, #d4784a)" }}>
        {icon || "◈"}
      </div>
      <h4 style={{ margin: "0 0 6px", fontSize: "15px", color: "var(--ink, #f3ece4)" }}>{title}</h4>
      <p style={{ margin: "0 0 16px", fontSize: "13px", color: "var(--ink-dim, #b7aaa0)", maxWidth: "420px" }}>
        {message}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
}

export function ErrorCard({
  title = "Telemetry Query Failed",
  message = "Unable to retrieve real-time service telemetry from API.",
  onRetry,
  style,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
  style?: CSSProperties;
}) {
  return (
    <div
      style={{
        padding: "20px 24px",
        borderRadius: "var(--radius, 14px)",
        border: "1px solid rgba(211, 106, 88, 0.35)",
        backgroundColor: "rgba(211, 106, 88, 0.08)",
        color: "var(--ink, #f3ece4)",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: "16px",
        ...style,
      }}
    >
      <div>
        <h4 style={{ margin: "0 0 4px", fontSize: "14px", color: "var(--signal-bad, #d36a58)" }}>{title}</h4>
        <p style={{ margin: 0, fontSize: "13px", color: "var(--ink-dim, #b7aaa0)" }}>{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="btn"
          style={{
            padding: "6px 14px",
            fontSize: "12px",
            borderRadius: "8px",
            border: "1px solid rgba(211, 106, 88, 0.5)",
            background: "rgba(211, 106, 88, 0.2)",
            color: "#ff8b7b",
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          Retry
        </button>
      )}
    </div>
  );
}
