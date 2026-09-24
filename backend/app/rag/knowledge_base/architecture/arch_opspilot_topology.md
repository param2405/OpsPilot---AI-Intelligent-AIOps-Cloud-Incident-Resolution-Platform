# Architecture Specification: OpsPilot System Topology and Event Flow

## System Overview & Design Principles
OpsPilot is an AI-powered autonomous incident resolution and observability platform designed for multi-region cloud workloads. The system achieves sub-second anomaly detection, dynamic sequence analysis, automated root cause synthesis, and human-in-the-loop remediation.

## Core Component Decomposition

### 1. Ingestion Engine & Telemetry Gateways
The Ingestion Engine receives telemetry across three distinct streams:
- Metric Telemetry: High-frequency Prometheus time-series ingested via OpenTelemetry collectors.
- Structured Log Stream: JSON formatted application logs transported over Fluentbit and vector daemons.
- Cloud Events & Alerts: PagerDuty, AWS CloudWatch, and Datadog webhooks routed via API Gateway.

### 2. Message Bus & Event Streaming Layer
Apache Kafka serves as the backbone event streaming bus:
- Topic `raw-telemetry`: High-throughput ingestion stream partitioned by `service_id` and `tenant_id` with 16 partitions per cluster.
- Topic `incident-alerts`: Normalized alert schema consumed by the correlation engine.
- Retention Policy: 7 days retention for raw telemetry, 30 days for incident alerts.

### 3. ML Inference & Sequence Anomaly Service
The ML subsystem operates in two distinct operational tiers:
- Fast Path (Tabular ML): LightGBM and Isolation Forest evaluating CPU, memory, and error rate vectors every 5 seconds.
- Deep Sequence Path (PyTorch Bi-LSTM / GRU): Evaluates temporal sequences of log event IDs to detect complex state transitions and error cascades that bypass static thresholding.

### 4. RAG Knowledge Layer & Vector Store
The RAG layer provides grounding knowledge to prevent LLM hallucinations:
- Document Store: PostgreSQL 16 storing raw Markdown, plain text, and PDF operational artifacts.
- Vector Engine: PostgreSQL `pgvector` extension indexing 128-dimensional dense semantic embeddings.
- Ingestion Chunker: Section-aware chunking preserving hierarchy with contextual headers (`[Title § Section]`).
- Retrieval: Hybrid retrieval combining dense cosine distance and lexical full-text search with Reciprocal Rank Fusion (RRF).

### 5. Autonomous Remediation Engine
Executes approved remediation actions through Ansible playbooks, Kubernetes operators, and AWS SSM agents. All remediation commands adhere to strict circuit-breaker policies and require mutual confirmation for disruptive actions.
