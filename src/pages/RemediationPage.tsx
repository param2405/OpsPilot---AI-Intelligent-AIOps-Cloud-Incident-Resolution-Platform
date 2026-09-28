import { RemediationControlCenter } from "../components/RemediationControlCenter";

export function RemediationPage() {
  return (
    <div style={{ display: "grid", gap: 24 }}>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <h2 style={{ margin: 0, fontSize: 20, color: "var(--ink)" }}>
            Human-In-The-Loop Remediation Console
          </h2>
          <span
            className="chip"
            style={{
              background: "rgba(212, 120, 74, 0.15)",
              color: "var(--filament)",
              fontWeight: 700,
            }}
          >
            Phase 9 · Safety Gateway
          </span>
        </div>
        <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--ink-dim)" }}>
          Authorize allowlisted SRE actions, inspect deterministic parameter boundaries, review simulation output, and audit all remediation history.
        </p>
      </div>

      <RemediationControlCenter />
    </div>
  );
}
