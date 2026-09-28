# OpsPilot AI — Containerization Architecture & Operations Guide (Phase 10)

## 1. Executive Summary

Phase 10 establishes a production-grade, containerized local development and deployment environment for OpsPilot AI. The stack packages all necessary microservices, data persistence stores, caching layers, experiment trackers, and background workers into an isolated, reproducible Docker Compose topology.

### Core Architectural Principles
- **Multi-Stage Builds**: Both backend and frontend utilize multi-stage Docker builds to separate compilation toolchains from runtime containers, minimizing attack surface and image size.
- **Non-Root Execution**: Backend and background worker containers run under an unprivileged user (`opspilot`, UID `10001`). Web assets run under Nginx unprivileged worker processes.
- **Zero Hardcoded Secrets**: All credentials and tokens are dynamically injected via environment variables with safe development defaults (`.env.example` / `.env`).
- **Health-Gated Startup Order**: Downstream services wait for upstream dependencies to pass readiness health checks (`condition: service_healthy`) before booting.
- **Graceful Shutdown**: All services intercept termination signals (`SIGTERM` / `SIGQUIT`) with configured grace periods ($15\text{s} \dots 30\text{s}$) to allow inflight requests and background transactions to commit cleanly.
- **Isolated Bridge Network**: Microservices communicate over a dedicated bridge network (`opspilot-net`) with internal service DNS resolution.

---

## 2. Container Topology & Service Catalog

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Docker Host Machine                             │
│                                                                        │
│   Public Ports:  80 / 5173 (Web)     8000 (API)      5000 (MLflow)     │
│                     │                    │                 │           │
│                     ▼                    ▼                 ▼           │
│  ┌───────────────────────┐   ┌──────────────────────┐  ┌────────────┐  │
│  │      opspilot-web     │──►│     opspilot-api     │  │  opspilot- │  │
│  │   (Nginx 1.27 SPA +   │   │  (FastAPI Python 3.12│  │   mlflow   │  │
│  │     Reverse Proxy)    │   │      Non-Root)       │  │ (Tracking) │  │
│  └───────────────────────┘   └──────────┬───────────┘  └─────┬──────┘  │
│                                         │                    │         │
│               ┌─────────────────────────┼────────────────────┘         │
│               │                         │                              │
│               ▼                         ▼                              │
│  ┌───────────────────────┐   ┌──────────────────────┐                  │
│  │   opspilot-postgres   │   │    opspilot-redis    │                  │
│  │ (pgvector/pgvector:16 │   │ (redis:7.2-alpine    │                  │
│  │  Relational Storage)  │   │  Cache & Rate Limit) │                  │
│  └───────────────────────┘   └──────────────────────┘                  │
│               ▲                         ▲                              │
│               │                         │                              │
│               └─────────────┬───────────┘                              │
│                             │                                          │
│               ┌─────────────┴───────────┐                              │
│               │     opspilot-worker     │                              │
│               │  (Background Anomaly &  │                              │
│               │   Telemetry Processor)  │                              │
│               └─────────────────────────┘                              │
│                                                                        │
│           Bridge Network: opspilot-net (Internal DNS)                  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Container Specifications

### 3.1 `opspilot-postgres`
- **Role**: Relational database storing services, metrics, structured logs, incident lifecycles, investigations, vector embeddings (pgvector), and Phase 9 remediation audit logs.
- **Base Image**: `pgvector/pgvector:pg16`
- **Port Mapping**: `${POSTGRES_PORT:-5432}:5432`
- **Persistent Volume**: `postgres_data:/var/lib/postgresql/data`
- **Environment Variables**:
  - `POSTGRES_USER`: `${POSTGRES_USER:-opspilot}`
  - `POSTGRES_PASSWORD`: `${POSTGRES_PASSWORD:-opspilot_dev_password}`
  - `POSTGRES_DB`: `${POSTGRES_DB:-opspilot}`
- **Health Check**:
  - Command: `pg_isready -U opspilot -d opspilot`
  - Interval: `5s` | Timeout: `5s` | Retries: `10` | Start Period: `10s`

### 3.2 `opspilot-redis`
- **Role**: In-memory caching, rate-limiting token bucket, and asynchronous queue broker for background worker jobs.
- **Base Image**: `redis:7.2-alpine`
- **Command**: `redis-server --appendonly yes`
- **Port Mapping**: `${REDIS_PORT:-6379}:6379`
- **Persistent Volume**: `redis_data:/data`
- **Health Check**:
  - Command: `redis-cli ping`
  - Interval: `5s` | Timeout: `3s` | Retries: `5` | Start Period: `5s`

### 3.3 `opspilot-mlflow`
- **Role**: Centralized ML experiment tracking server, hyperparameter logging, and model registry for anomaly detection, incident classification, and severity prediction models.
- **Base Image**: `python:3.12-slim`
- **Command**: `mlflow server --backend-store-uri sqlite:////mlflow/mlflow.db --default-artifact-root /mlflow/artifacts --host 0.0.0.0 --port 5000`
- **Port Mapping**: `${MLFLOW_PORT:-5000}:5000`
- **Persistent Volume**: `mlflow_data:/mlflow`
- **Health Check**:
  - Command: `python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"`
  - Interval: `10s` | Timeout: `5s` | Retries: `10` | Start Period: `20s`

### 3.4 `opspilot-api`
- **Role**: Core FastAPI backend serving REST APIs, running machine learning inference, orchestrating LangGraph incident investigation agents, and managing Phase 9 Human-In-The-Loop remediation workflows.
- **Build**: Multi-stage Dockerfile (`backend/Dockerfile`):
  - Stage 1 (`builder`): Compiles C-extensions and wheels in virtual environment `/opt/venv`.
  - Stage 2 (`runtime`): Copies `/opt/venv`, installs runtime `libpq5` & `curl`, runs as non-root user `opspilot:10001`.
- **Port Mapping**: `${API_PORT:-8000}:8000`
- **Environment Variables**:
  - `POSTGRES_HOST=postgres`, `POSTGRES_PORT=5432`, `DATABASE_URL=...`
  - `REDIS_HOST=redis`, `REDIS_PORT=6379`
  - `MLFLOW_TRACKING_URI=http://mlflow:5000`
- **Dependencies**: `postgres` (healthy), `redis` (healthy), `mlflow` (healthy)
- **Health Check**:
  - Command: `curl -f http://localhost:8000/api/v1/health || exit 1`
  - Interval: `10s` | Timeout: `5s` | Retries: `5` | Start Period: `25s`
- **Graceful Shutdown**: `stop_signal: SIGTERM`, `stop_grace_period: 30s`

### 3.5 `opspilot-worker`
- **Role**: Asynchronous background worker executing continuous telemetry health checks, incident SLA tracking, queue processing, and periodic maintenance loops.
- **Build**: Same multi-stage image as backend (`backend/Dockerfile`).
- **Command**: `python -m app.jobs.worker`
- **Security**: Runs as unprivileged non-root user `opspilot:10001`.
- **Environment Variables**:
  - `WORKER_INTERVAL_SECONDS=10`
  - `WORKER_HEARTBEAT_FILE=/tmp/opspilot/worker_heartbeat`
- **Dependencies**: `postgres` (healthy), `redis` (healthy), `api` (healthy)
- **Health Check**:
  - Command: `test -f /tmp/opspilot/worker_heartbeat || exit 1`
  - Interval: `15s` | Timeout: `5s` | Retries: `3` | Start Period: `15s`
- **Graceful Shutdown**: Intercepts `SIGTERM` and `SIGINT`, finishes current loop tick, cleans up heartbeat file, and exits cleanly within `stop_grace_period: 30s`.

### 3.6 `opspilot-web`
- **Role**: Production React 19 Single Page Application (SPA) served via Nginx with embedded reverse proxy routing `/api/` traffic directly to `http://api:8000/api/`.
- **Build**: Multi-stage Dockerfile (`Dockerfile`):
  - Stage 1 (`build`): `node:22-alpine` installs dependencies via `npm ci` and compiles static bundle via `npm run build`.
  - Stage 2 (`runtime`): `nginx:1.27-alpine` serves static assets with Gzip compression and handles client-side SPA routing (`try_files $uri $uri/ /index.html`).
- **Port Mapping**:
  - `80:80`: Standard HTTP web entrypoint.
  - `5173:80`: Development convenience mapping for Vite parity.
- **Dependencies**: `api` (healthy)
- **Health Check**:
  - Command: `curl -f http://localhost:80/healthz || exit 1`
  - Interval: `15s` | Timeout: `5s` | Retries: `3` | Start Period: `10s`
- **Graceful Shutdown**: `stop_signal: SIGQUIT`, `stop_grace_period: 15s`

---

## 4. Networking, Ports & Volumes

### 4.1 Internal Service DNS & Port Catalog

| Service Container | Internal Hostname | Internal Port | Host Port Binding | Protocol | Purpose |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `opspilot-postgres` | `postgres` | `5432` | `5432` | TCP | Relational DB & vector store |
| `opspilot-redis` | `redis` | `6379` | `6379` | TCP | Cache, rate limiter, task queue |
| `opspilot-mlflow` | `mlflow` | `5000` | `5000` | HTTP | MLflow tracking server |
| `opspilot-api` | `api` | `8000` | `8000` | HTTP | FastAPI REST & Orchestration |
| `opspilot-worker` | `worker` | — | — | Internal | Background job processor |
| `opspilot-web` | `web` | `80` | `80`, `5173` | HTTP | Nginx Frontend & Reverse Proxy |

### 4.2 Persistent Volumes

| Volume Name | Driver | Container Mount Path | Stored Data |
| :--- | :--- | :--- | :--- |
| `postgres_data` | `local` | `/var/lib/postgresql/data` | PostgreSQL tables, indexes, WAL logs, pgvector embeddings. |
| `redis_data` | `local` | `/data` | Redis Append-Only File (`appendonly.aof`) snapshotting cache. |
| `mlflow_data` | `local` | `/mlflow` | SQLite database (`mlflow.db`) and trained model artifact files. |

---

## 5. Startup Order & Dependency Graph

Containers boot deterministically using Docker Compose v2 health conditions:

```
Step 1: Core Datastores
  ├─ postgres (waits until pg_isready succeeds)
  ├─ redis    (waits until redis-cli ping succeeds)
  └─ mlflow   (waits until http://localhost:5000/health returns 200)

Step 2: API Application Server
  └─ api (waits for postgres, redis, and mlflow to become HEALTHY)
         (runs DB migrations and initializes model registries)

Step 3: Consumer Services
  ├─ worker (waits for api, postgres, and redis to become HEALTHY)
  └─ web    (waits for api to become HEALTHY before serving traffic)
```

This dependency chain guarantees that the frontend never receives 502 Bad Gateway errors upon initial boot, and the background worker never connects to an uninitialized database.

---

## 6. Operational CLI Runbook

All commands are executed from the repository root directory.

### 6.1 Build Images
Build all container images using local build contexts and multi-stage layer caches:
```bash
# Build all images cleanly
docker compose build

# Build without cache (force rebuild)
docker compose build --no-cache
```

### 6.2 Start the Platform
Start all services in detached background mode:
```bash
# Start all containers in background
docker compose up -d

# Verify container health status
docker compose ps
```

### 6.3 Monitor Logs
Stream unified real-time logs across all services or target specific containers:
```bash
# Follow unified logs from all services
docker compose logs -f

# Follow logs from the FastAPI backend only
docker compose logs -f api

# Follow logs from the background worker
docker compose logs -f worker

# Follow Nginx access and error logs
docker compose logs -f web
```

### 6.4 Stop the Platform
Stop all running containers while preserving data volumes:
```bash
# Graceful shutdown (sends SIGTERM/SIGQUIT with 30s grace period)
docker compose down
```

### 6.5 Reset Local Environment
Wipe all containers, networks, and persistent data volumes to return to a completely clean slate:
```bash
# Stop containers and destroy all named persistent volumes
docker compose down -v --remove-orphans

# Rebuild and start fresh
docker compose up -d --build
```

---

## 7. Failure Mode & Resilience Analysis

What happens when an individual container experiences failure or crash?

| Failing Container | Impact on Ecosystem | Automated Recovery & Resilience Behavior |
| :--- | :--- | :--- |
| **`postgres` fails** | • API read/write operations fail with DB connection error.<br>• Worker pauses and logs retry warnings. | • Docker automatically restarts Postgres (`restart: unless-stopped`).<br>• SQLAlchemy pool discards stale connections and reconnects automatically via psycopg backoff.<br>• Data is preserved in persistent volume `postgres_data`. |
| **`redis` fails** | • In-memory rate limiting and task queueing temporarily degrade. | • Docker restarts Redis container.<br>• Redis recovers dataset from `appendonly.aof` stored in `redis_data`.<br>• Backend falls back gracefully or reconnects on next tick. |
| **`mlflow` fails** | • Model tracking metric logging is temporarily buffered or skipped.<br>• Live inference continues unaffected using local champion weights. | • Docker restarts MLflow.<br>• State and run artifacts persist in `mlflow_data`.<br>• ML inference service gracefully degrades without crashing. |
| **`api` fails** | • Frontend UI displays error toasts or retries.<br>• Worker loop pauses API-dependent tasks. | • Docker restarts `opspilot-api`.<br>• Nginx buffers requests or returns transient 502 until API healthcheck passes.<br>• Stateless container resumes handling requests within 10 seconds. |
| **`worker` fails** | • Background telemetry polling and scheduled evaluations pause.<br>• User-facing APIs and Dashboard remain 100% operational. | • Docker restarts `opspilot-worker`.<br>• Heartbeat file is recreated.<br>• Worker resumes polling active incidents from PostgreSQL. |
| **`web` fails** | • Browser requests to port 80 / 5173 fail to load the SPA. | • Docker restarts `opspilot-web`.<br>• Nginx re-reads configuration and resumes serving within 2 seconds. |

---

## 8. Verification & Validation Checklist

- [x] **`docker-compose.yml`**: Validated syntax via `docker compose config` (exited with code 0).
- [x] **Multi-Stage Frontend**: `Dockerfile` implements `build` (Node 22) + `runtime` (Nginx 1.27) with healthcheck.
- [x] **Multi-Stage Backend**: `backend/Dockerfile` implements `builder` + `runtime` with non-root user `opspilot:10001` and healthcheck.
- [x] **Background Worker**: `backend/app/jobs/worker.py` implemented with graceful shutdown and heartbeat healthcheck.
- [x] **Datastores Configured**: `pgvector:pg16` and `redis:7.2-alpine` with persistent volumes and health probes.
- [x] **MLflow Integration**: `mlflow` service configured with SQLite backend store and local artifact repository.
- [x] **Zero Secrets in Dockerfiles**: Fully driven by `.env.example` / `.env` variables.
- [x] **Nginx Reverse Proxy**: Configured in `nginx.conf` for unified port 80 access without CORS issues.
