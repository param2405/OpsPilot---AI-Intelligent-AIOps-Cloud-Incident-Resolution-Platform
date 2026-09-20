import { SignalBoard } from "../components/health/SignalBoard";

export function FoundationPage() {
  return (
    <div className="layout">
      <section className="panel">
        <p className="lede">
          This console is the Phase 1 shell: routing, visual language, and a live check against
          the FastAPI process and PostgreSQL. Anomaly detection, classification, RAG, and agents
          are not implemented here.
        </p>
        <div className="facts">
          <div className="fact">
            <b>API</b>
            FastAPI · /api/v1
          </div>
          <div className="fact">
            <b>Store</b>
            PostgreSQL · connectivity only
          </div>
          <div className="fact">
            <b>UI</b>
            React · Vite · typed client
          </div>
        </div>
      </section>
      <SignalBoard />
    </div>
  );
}
