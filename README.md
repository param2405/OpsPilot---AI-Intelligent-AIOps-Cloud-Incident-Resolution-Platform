# OpsPilot AI

Intelligent AIOps and cloud incident resolution platform.

**Current status: Phase 1 — project foundation and architecture.**  
This repository does not yet contain machine learning, deep learning, RAG, agents, or AWS deployment.

## What Phase 1 includes

- FastAPI backend organized by responsibility (`api`, `services`, `db`, `schemas`, …)
- React + TypeScript frontend with a real health console and reserved routes for later surfaces
- PostgreSQL as the only local infrastructure dependency
- Liveness and readiness HTTP endpoints under `/api/v1`
- Docker Compose for local development
- Tests for backend health/config and the frontend shell

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

- Web UI: http://localhost:5173
- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs
- Liveness: http://localhost:8000/api/v1/health
- Readiness: http://localhost:8000/api/v1/health/ready

PostgreSQL-only (API and UI run on the host):

```bash
docker compose up postgres
```

Then follow `docs/development.md` for host-side Python and Node commands.

## Documentation

| File | Contents |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | System shape and future layers |
| [docs/development.md](docs/development.md) | Install, env, run, test |
| [docs/decisions.md](docs/decisions.md) | ADR-style technology choices |

## Tests

```bash
# backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest

# frontend
cd frontend
npm install
npm test
```

## What is intentionally not here

No trained models, no vector store, no LangGraph graph, no incident tables, no fake dashboards pretending to show production telemetry.
