import type { CSSProperties, ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  kicker?: string;
  className?: string;
  style?: CSSProperties;
  onClick?: () => void;
  hoverable?: boolean;
}

export function Card({
  children,
  title,
  subtitle,
  actions,
  kicker,
  className = "",
  style,
  onClick,
  hoverable = false,
}: CardProps) {
  const isClickable = Boolean(onClick) || hoverable;

  return (
    <section
      className={`panel ${isClickable ? "card-hoverable" : ""} ${className}`}
      onClick={onClick}
      style={{
        borderRadius: "var(--radius, 16px)",
        border: "1px solid var(--line, rgba(255,255,255,0.1))",
        background: "linear-gradient(180deg, rgba(255, 255, 255, 0.02) 0%, rgba(255, 255, 255, 0) 100%), var(--bg-panel, #211c17)",
        padding: "20px 24px",
        position: "relative",
        transition: "border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease",
        cursor: isClickable ? "pointer" : "default",
        ...style,
      }}
    >
      {(title || kicker || actions) && (
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: "16px",
            borderBottom: "1px solid var(--line, rgba(255,255,255,0.06))",
            paddingBottom: "12px",
          }}
        >
          <div>
            {kicker && (
              <span
                style={{
                  display: "block",
                  fontSize: "11px",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--filament, #d4784a)",
                  marginBottom: "4px",
                }}
              >
                {kicker}
              </span>
            )}
            {title && (
              <h3
                style={{
                  margin: 0,
                  fontSize: "16px",
                  fontWeight: 600,
                  color: "var(--ink, #f3ece4)",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                {title}
              </h3>
            )}
            {subtitle && (
              <p
                style={{
                  margin: "4px 0 0",
                  fontSize: "13px",
                  color: "var(--ink-dim, #b7aaa0)",
                }}
              >
                {subtitle}
              </p>
            )}
          </div>
          {actions && <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
