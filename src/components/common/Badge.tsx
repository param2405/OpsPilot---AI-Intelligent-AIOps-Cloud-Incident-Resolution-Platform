import type { CSSProperties, ReactNode } from "react";

export type BadgeVariant =
  | "p1"
  | "p2"
  | "p3"
  | "p4"
  | "success"
  | "normal"
  | "warning"
  | "danger"
  | "critical"
  | "neutral"
  | "accent"
  | "purple";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  pulse?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
  style?: CSSProperties;
}

const variantStyles: Record<BadgeVariant, { bg: string; color: string; border: string }> = {
  p1: { bg: "rgba(224, 76, 76, 0.15)", color: "#ff6b6b", border: "rgba(224, 76, 76, 0.4)" },
  p2: { bg: "rgba(224, 130, 76, 0.15)", color: "#ffa96b", border: "rgba(224, 130, 76, 0.4)" },
  p3: { bg: "rgba(201, 162, 39, 0.15)", color: "#ffd86b", border: "rgba(201, 162, 39, 0.4)" },
  p4: { bg: "rgba(76, 154, 224, 0.15)", color: "#6bb9ff", border: "rgba(76, 154, 224, 0.4)" },
  success: { bg: "rgba(143, 191, 159, 0.15)", color: "var(--sage, #8fbf9f)", border: "rgba(143, 191, 159, 0.3)" },
  normal: { bg: "rgba(143, 191, 159, 0.15)", color: "var(--sage, #8fbf9f)", border: "rgba(143, 191, 159, 0.3)" },
  warning: { bg: "rgba(201, 162, 39, 0.15)", color: "var(--signal-wait, #c9a227)", border: "rgba(201, 162, 39, 0.3)" },
  danger: { bg: "rgba(211, 106, 88, 0.15)", color: "var(--signal-bad, #d36a58)", border: "rgba(211, 106, 88, 0.3)" },
  critical: { bg: "rgba(211, 106, 88, 0.15)", color: "var(--signal-bad, #d36a58)", border: "rgba(211, 106, 88, 0.3)" },
  neutral: { bg: "rgba(255, 255, 255, 0.05)", color: "var(--ink-dim, #b7aaa0)", border: "var(--line, rgba(255,255,255,0.1))" },
  accent: { bg: "rgba(212, 120, 74, 0.15)", color: "var(--filament, #d4784a)", border: "rgba(212, 120, 74, 0.4)" },
  purple: { bg: "rgba(168, 85, 247, 0.15)", color: "#c084fc", border: "rgba(168, 85, 247, 0.4)" },
};

export function Badge({
  children,
  variant = "neutral",
  pulse = false,
  size = "md",
  className = "",
  style,
}: BadgeProps) {
  const current = variantStyles[variant] || variantStyles.neutral;

  const sizeStyle =
    size === "sm"
      ? { fontSize: "11px", padding: "2px 6px", height: "18px" }
      : size === "lg"
      ? { fontSize: "13px", padding: "4px 12px", height: "26px" }
      : { fontSize: "12px", padding: "3px 9px", height: "22px" };

  return (
    <span
      className={`op-badge ${className}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        borderRadius: "9999px",
        fontWeight: 600,
        fontFamily: "var(--mono, monospace)",
        letterSpacing: "0.03em",
        backgroundColor: current.bg,
        color: current.color,
        border: `1px solid ${current.border}`,
        ...sizeStyle,
        ...style,
      }}
    >
      {pulse && (
        <span
          style={{
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            backgroundColor: current.color,
            boxShadow: `0 0 8px ${current.color}`,
            animation: "pulse 1.8s infinite ease-in-out",
          }}
        />
      )}
      {children}
    </span>
  );
}

export function severityToVariant(severity: string): BadgeVariant {
  const s = severity.toUpperCase();
  if (s.includes("CRITICAL") || s.includes("P1")) return "p1";
  if (s.includes("HIGH") || s.includes("P2")) return "p2";
  if (s.includes("MEDIUM") || s.includes("P3")) return "p3";
  if (s.includes("LOW") || s.includes("P4")) return "p4";
  return "neutral";
}

export function statusToVariant(status: string): BadgeVariant {
  const s = status.toUpperCase();
  if (s === "RESOLVED" || s === "READY" || s === "HEALTHY" || s === "SUCCESS" || s === "COMPLETED") return "success";
  if (s === "INVESTIGATING" || s === "IDENTIFIED" || s === "DEGRADED") return "warning";
  if (s === "CRITICAL" || s === "FAILED" || s === "UNAVAILABLE") return "danger";
  if (s === "MITIGATED") return "purple";
  return "neutral";
}
