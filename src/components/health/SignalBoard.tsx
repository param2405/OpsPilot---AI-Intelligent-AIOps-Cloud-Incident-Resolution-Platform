import { useEffect, useState } from "react";
import { getLiveness, getReadiness, type HealthResponse, type ReadinessResponse } from "../../api/health";

type LoadState =
  | { kind: "loading" }
  | { kind: "ok"; live: HealthResponse; ready: ReadinessResponse }
  | { kind: "error"; message: string };

function tone(ok: boolean): "ok" | "bad" {
  return ok ? "ok" : "bad";
}

export function SignalBoard() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        const [live, ready] = await Promise.all([
          getLiveness(controller.signal),
          getReadiness(controller.signal),
        ]);
        setState({ kind: "ok", live, ready });
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
        const message = error instanceof Error ? error.message : "Unable to reach the API.";
        setState({ kind: "error", message });
      }
    }

    void load();
    const id = window.setInterval(() => {
      void load();
    }, 8000);

    return () => {
      controller.abort();
      window.clearInterval(id);
    };
  }, []);

  const apiUp = state.kind === "ok";
  const dbUp = state.kind === "ok" && state.ready.database.connected;
  const ringClass = state.kind === "loading" ? "wait" : apiUp ? "ok" : "bad";

  return (
    <section className="panel beam instrument" aria-live="polite">
      <div className="ring-wrap">
        <svg className="ring" viewBox="0 0 180 180" aria-hidden="true">
          <circle className="ring-track" cx="90" cy="90" r="78" />
          <circle className={`ring-value ${ringClass}`} cx="90" cy="90" r="78" />
        </svg>
        <div className="ring-center">
          <strong>{apiUp ? "Live" : state.kind === "loading" ? "…" : "Down"}</strong>
          <span>API path</span>
        </div>
      </div>
      <div className="signals">
        <div className="signal">
          <span className="pill">
            <i className={`dot ${state.kind === "loading" ? "" : tone(apiUp)}`} />
            Process
          </span>
          <small>
            {state.kind === "ok" ? `${state.live.status} · ${state.live.version}` : state.kind === "loading" ? "polling" : "unreachable"}
          </small>
        </div>
        <div className="signal">
          <span className="pill">
            <i className={`dot ${state.kind === "loading" ? "" : tone(dbUp)}`} />
            PostgreSQL
          </span>
          <small>
            {state.kind === "ok"
              ? state.ready.database.detail
              : state.kind === "loading"
                ? "waiting on /health/ready"
                : "not checked"}
          </small>
        </div>
        <div className="signal">
          <span className="pill">
            <i className={`dot ${state.kind === "ok" ? "ok" : ""}`} />
            Environment
          </span>
          <small>{state.kind === "ok" ? state.live.environment : "unknown"}</small>
        </div>
      </div>
      {state.kind === "error" ? <p className="error-line">{state.message}</p> : null}
    </section>
  );
}
