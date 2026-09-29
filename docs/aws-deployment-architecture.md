# OpsPilot AI — Production AWS Deployment Architecture (Phase 11)

## 1. Architectural Overview & Design Philosophy

OpsPilot AI is an enterprise-grade, intelligent AIOps and cloud incident resolution platform. Phase 11 transitions OpsPilot AI from local containerization into a resilient, production-ready, highly available, and cost-optimized AWS cloud topology.

### 1.1 Core Architectural Principles
- **Managed Services First**: Offload undifferentiated operational overhead (OS patching, failover automation, database replication, backup retention) by utilizing Amazon ECS with AWS Fargate, Amazon RDS PostgreSQL, Amazon ElastiCache for Redis, AWS Secrets Manager, and Amazon CloudFront.
- **Serverless Compute**: Avoid running idle EC2 instances 24/7. ECS on AWS Fargate charges purely per vCPU and memory allocated per second, scaling down to baseline during quiet hours and elastically scaling up during incident bursts.
- **Static Edge Delivery**: Serve the React frontend Single Page Application (SPA) from Amazon S3 via Amazon CloudFront with Origin Access Control (OAC). This eliminates 24/7 web server container instances, dropping frontend compute cost to pennies per month while delivering sub-50ms latency globally with AWS Shield DDoS protection.
- **No Hardcoded Credentials**: Zero secrets, tokens, or private keys exist in version control or container images. All credentials are encrypted with AWS KMS and injected dynamically into container runtime environments via AWS Secrets Manager.
- **Defense in Depth**: Every tier resides in its own isolated network zone with strict, unidirectional security group references. The database and Redis cache have zero internet exposure.
- **Reproducibility via IaC**: The entire infrastructure is declaratively defined in modular, parameterized Terraform with environment configurations for `development`, `staging`, and `production`.

---

## 2. End-to-End System Topology

```
                                    ┌───────────────────────┐
                                    │    Internet Users     │
                                    │  (DevOps / SRE Team)  │
                                    └──────────┬────────────┘
                                               │ HTTPS (TLS 1.3 / Port 443)
                                               ▼
                              ┌─────────────────────────────────┐
                              │     Amazon CloudFront (CDN)     │
                              │     Global Edge Network         │
                              └───────┬─────────────────┬───────┘
                     Static Assets    │                 │ Dynamic API Calls
                   (HTML/JS/CSS/SVG)  │                 │ Path: /api/*
                                      ▼                 ▼
          ┌─────────────────────────────┐    ┌─────────────────────────────────┐
          │      Amazon S3 Bucket       │    │   Application Load Balancer     │
          │    (Frontend Web Build)     │    │   (ALB in Public Subnets)       │
          │ Origin Access Control (OAC) │    └────────────────┬────────────────┘
          └─────────────────────────────┘                     │ Port 8000
                                                              ▼
══════════════════════════════════════════════════════════════════════════════════════════════════
 AWS Virtual Private Cloud (VPC: 10.0.0.0/16)
══════════════════════════════════════════════════════════════════════════════════════════════════
 ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
 │ PRIVATE APPLICATION SUBNETS (AZ-a & AZ-b)                                                   │
 │ (No Public IPs, Egress via NAT Gateway / S3 VPC Gateway Endpoint)                           │
 │                                                                                             │
 │   ┌───────────────────────────────────┐       ┌───────────────────────────────────┐         │
 │   │  Amazon ECS Fargate Cluster       │       │  Amazon ECS Fargate Worker        │         │
 │   │  Service: opspilot-api            │       │  Service: opspilot-worker         │         │
 │   │  (FastAPI Backend / Auto-scaled)  │       │  (Incident SLA & Anomaly Loops)   │         │
 │   │  Non-root UID 10001               │       │  Non-root UID 10001               │         │
 │   └─────────┬─────────────────────────┘       └─────────┬─────────────────────────┘         │
 └─────────────┼───────────────────────────────────────────┼───────────────────────────────────┘
               │ Port 5432 (Postgres)                      │ Port 6379 (Redis)
               ▼                                           ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
 │ PRIVATE ISOLATED DATABASE SUBNETS (AZ-a & AZ-b)                                             │
 │ (Strictly Isolated, No Internet Route, Ingress restricted to ECS Security Group)           │
 │                                                                                             │
 │   ┌───────────────────────────────────┐       ┌───────────────────────────────────┐         │
 │   │  Amazon RDS PostgreSQL 16         │       │  Amazon ElastiCache Redis         │         │
 │   │  (pgvector enabled / Encrypted)   │       │  (In-Memory Cache & Job Queue)    │         │
 │   │  Multi-AZ (Prod) / Single-AZ(Dev) │       │  In-Transit & At-Rest Encryption  │         │
 │   └───────────────────────────────────┘       └───────────────────────────────────┘         │
 └─────────────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
          ┌──────────────────────────────────────────────────────────────────┐
          │                    Amazon S3 Artifact Bucket                     │
          │  - RAG Runbooks & Knowledge Base Documents                       │
          │  - MLflow Model Checkpoints & Artifact Registry                  │
          │  - Incident Diagnostic Dumps & Postmortems                       │
          │  (SSE-KMS Encryption, Object Versioning, Intelligent Tiering)    │
          └──────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Architectural Components

### 3.1 Frontend Tier: Amazon CloudFront & Amazon S3
- **Component**: React + TypeScript Single Page Application (Vite build output).
- **Hosting Strategy**: Uploaded to a private Amazon S3 bucket (`opspilot-frontend-${env}-${account_id}`).
- **Access Control**: Bucket access is restricted exclusively to CloudFront using **Origin Access Control (OAC)**. Direct S3 public access is blocked at the bucket and account level (`BlockPublicAcls = true`, `BlockPublicPolicy = true`, `IgnorePublicAcls = true`, `RestrictPublicBuckets = true`).
- **CDN Edge Routing**:
  - `/*` (Default Cache Behavior): Routes to the S3 bucket. Optimized caching headers with Brotli and Gzip compression.
  - `/api/*`: Routes to the Application Load Balancer (ALB). Caching disabled (`Cache-Control: no-cache, no-store`), all HTTP methods (`GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE`) forwarded, and headers (`Authorization`, `Host`) passed through.
  - SPA Routing Support: Custom error response intercepts HTTP 403/404 from S3 and returns `/index.html` with HTTP 200 to allow client-side React Router navigation.

### 3.2 Compute Tier: Amazon ECS on AWS Fargate
- **Amazon ECS Cluster**: Manages container orchestration without host instance management.
- **`opspilot-api` Service**:
  - Runs FastAPI application container (`uvicorn app.main:app --host 0.0.0.0 --port 8000`).
  - Placed in private application subnets across multiple AZs.
  - Registered to the Application Load Balancer Target Group with health check path `/api/v1/health`.
  - Configured with rolling zero-downtime deployments (`minimum_healthy_percent = 100`, `maximum_percent = 200`).
  - Auto-scaled via AWS Application Auto Scaling based on Target Tracking:
    - Target CPU utilization: 70%
    - Target ALB request count per target: 1000 requests/minute.
- **`opspilot-worker` Service**:
  - Runs background worker container (`python -m app.jobs.worker`).
  - Polls active incidents, calculates SLA breaches, monitors anomaly streams, and manages background tasks.
  - Graceful shutdown handles `SIGTERM` signals with a 30-second grace window to ensure running transactions complete.
  - Autoscaled based on queue depth / CPU utilization.

### 3.3 Database Tier: Amazon RDS PostgreSQL (with pgvector)
- **Engine**: PostgreSQL 16.
- **Vector Search Support**: Custom DB Parameter Group enables `pgvector` (`shared_preload_libraries = "pgvector"`). Supports OpsPilot's RAG knowledge embeddings, incident vector retrieval, and runbook similarity lookups.
- **High Availability**:
  - **Production**: Multi-AZ deployment across AZ-a and AZ-b with synchronous standby replication and automatic failover (< 60 seconds).
  - **Development / Staging**: Single-AZ deployment on cost-effective ARM Graviton2 (`db.t4g.micro` or `db.t4g.small`).
- **Storage**: General Purpose SSD (`gp3`) starting at 20 GB with Storage Auto-Scaling up to 100 GB to prevent disk exhaustion.
- **Disaster Recovery**: Automated daily snapshots retained for 30 days (production) or 7 days (development), with point-in-time recovery (PITR) to any second within the retention window. Deletion protection is strictly enforced.

### 3.4 In-Memory Cache & Queue Tier: Amazon ElastiCache for Redis
- **Engine**: Redis 7.2 (or Valkey).
- **Role**: Rate limiting, distributed locking for incident triage actions, short-term metric caching, and background task signaling.
- **Security**: In-transit TLS encryption, at-rest KMS encryption, and token authentication (`AUTH`).

### 3.5 Artifact Storage Tier: Amazon S3
- **Bucket**: `opspilot-artifacts-${env}-${region}-${account_id}`.
- **Role**: Durable, immutable object storage for:
  - Markdown/PDF Runbooks ingested into the RAG pipeline.
  - MLflow model binaries, scaler pickles, and PyTorch checkpoint weights.
  - Postmortem incident analysis export files and telemetry captures.
- **Security**: Server-Side Encryption with AWS KMS (SSE-KMS) using a dedicated Customer Managed Key (CMK), S3 Block Public Access enabled across all four controls, and S3 Bucket Versioning enabled to prevent accidental overwrites or malicious deletion.
- **Lifecycle Optimization**:
  - Automatic transition to S3 Intelligent-Tiering after 30 days.
  - Non-current versions transitioned to S3 Glacier Flexible Retrieval after 90 days.
  - Non-current versions expired after 365 days.
  - Abort incomplete multipart uploads after 7 days.

---

## 4. Eight Critical Architecture Requirements Addressed

### Requirement 1: Architecture Explanation
The architecture separates presentation, API processing, background execution, and persistence into clear horizontal tiers. Public entry is unified through CloudFront at edge locations, shielding internal AWS infrastructure. Dynamic requests cross the ALB into stateless Fargate containers in private subnets. Stateful relational data and vectors are stored in managed RDS PostgreSQL with pgvector, and high-throughput transient state is stored in ElastiCache Redis. Unstructured artifacts are stored in encrypted S3 buckets.

### Requirement 2: Expected Costs & Cost-Control Considerations

| Service | Development Tier (Monthly Est.) | Production Tier (Monthly Est.) | Cost-Control Strategy |
| :--- | :--- | :--- | :--- |
| **CloudFront + S3 (Web)** | ~$0.50 | ~$3.00 - $10.00 | S3 pay-per-request; CloudFront free tier covers 1TB transfer and 10M requests. |
| **ECS Fargate (API & Worker)** | ~$15.00 (Fargate Spot: 0.25 vCPU, 0.5GB) | ~$45.00 - $120.00 (Auto-scaled 2-6 tasks) | Fargate Spot for non-critical/dev tasks (70% savings); precise CPU/memory sizing; off-hours scaling. |
| **Application Load Balancer** | ~$18.00 (1 ALB) | ~$22.00 (1 ALB + LCU) | Consolidate API routing onto a single ALB with path-based routing. |
| **NAT Gateway** | ~$32.00 (1 single-AZ NAT GW) | ~$64.00 (2 multi-AZ NAT GW) | Single NAT in dev; S3 Gateway Endpoint (FREE) to route artifact traffic off the NAT Gateway. |
| **RDS PostgreSQL (pgvector)** | ~$15.00 (`db.t4g.micro`, Single-AZ) | ~$85.00 (`db.t4g.medium` or `db.m6g.large`, Multi-AZ) | Graviton2 ARM (20% cheaper); gp3 storage with baseline 3000 IOPS at no extra charge; storage autoscaling. |
| **ElastiCache Redis** | ~$13.00 (`cache.t4g.micro`) | ~$35.00 (`cache.t4g.small`, Multi-AZ) | Graviton2 ARM instances; scale node count only when eviction rate increases. |
| **S3 (Artifacts)** | ~$0.50 (< 10GB) | ~$5.00 - $15.00 | S3 Intelligent-Tiering, Glacier archival, and incomplete multipart upload cleanup. |
| **CloudWatch & Logs** | ~$3.00 | ~$15.00 - $30.00 | Strict retention policies (14 days dev, 30 days staging, 90 days prod); targeted metric alarms. |
| **Secrets Manager & KMS** | ~$1.50 (3 secrets + 1 CMK) | ~$3.00 | Secrets consolidation; CMK key reuse across services. |
| **Total Estimated Cost** | **~$98.50 / month** | **~$277.00 - ~$398.00 / month** | Full high-availability enterprise capability at startup cost. |

#### Specific Cost Control Rules Implemented in Code:
1. **S3 Gateway Endpoint**: S3 traffic flows over the internal AWS backbone free of charge, avoiding standard NAT Gateway data transfer rates ($0.045/GB).
2. **Fargate Spot**: Configured as an optional capacity provider for development and worker workloads to capture up to 70% savings.
3. **Graviton Instances (`t4g` series)**: Utilized for both RDS and ElastiCache to provide superior price-to-performance over Intel x86 alternatives.
4. **Log Retention Limits**: CloudWatch logs expire automatically after 14 days in development, preventing unbounded log accumulation costs.

### Requirement 3: Security Boundaries
1. **Edge Perimeter**: CloudFront acts as the public perimeter with AWS Shield Standard DDoS mitigation, enforcing HTTPS (TLS 1.2/1.3) and blocking direct IP-based access to S3.
2. **Network Perimeter**: Internet traffic can only reach the Application Load Balancer on ports 80/443. All compute and database workloads are completely shielded in private subnets.
3. **Application Layer Perimeter**:
   - Containers run as non-root user `opspilot` (UID `10001`).
   - Read-only root file systems where possible, with ephemeral storage limited to `/tmp`.
   - Inbound traffic to FastAPI is permitted only from the ALB security group.
4. **Data Layer Perimeter**:
   - RDS and Redis security groups only accept ingress from the ECS Task security group.
   - All data at rest is encrypted with customer-managed AWS KMS keys.
   - All data in transit is encrypted using TLS.

### Requirement 4: Network Boundaries
The VPC is partitioned into three distinct network tiers across two Availability Zones:

```
VPC CIDR (e.g. 10.0.0.0/16)
 ├── Public Subnets (10.0.1.0/24, 10.0.2.0/24)
 │    ├── Internet Gateway Attached
 │    ├── Hosts ALB and NAT Gateways
 │    └── Routes 0.0.0.0/0 to Internet Gateway
 │
 ├── Private Application Subnets (10.0.10.0/24, 10.0.20.0/24)
 │    ├── Hosts ECS Fargate Tasks (API & Worker)
 │    ├── No Public IP Assignment
 │    ├── Routes 0.0.0.0/0 to NAT Gateway
 │    └── Routes com.amazonaws.region.s3 to S3 Gateway Endpoint
 │
 └── Private Isolated Database Subnets (10.0.30.0/24, 10.0.40.0/24)
      ├── Hosts RDS PostgreSQL and ElastiCache Redis
      ├── No Internet Gateway or NAT Gateway routes
      └── Strictly unreachable from the internet under all conditions
```

### Requirement 5: Secrets Management
- **Zero Plaintext Secrets**: No secrets exist in Git repositories, Dockerfiles, Terraform state in plaintext, or environment files.
- **AWS Secrets Manager**: Dedicated secret objects are provisioned:
  - `/${environment}/opspilot/database`: Master database username, password, host, and port.
  - `/${environment}/opspilot/redis`: Redis auth token and host endpoint.
  - `/${environment}/opspilot/application`: JWT secret key, API keys, encryption seeds.
- **Runtime Secret Injection via ECS**: Secrets are fetched directly at task initialization by the Amazon ECS container agent using the ECS Task Execution Role and injected into container memory as environment variables (`POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `DATABASE_URL`).
- **Encryption**: Secrets are encrypted at rest using an AWS KMS Customer Managed Key.
- **Rotation Capability**: Configured to support AWS Secrets Manager automated rotation via Lambda.

### Requirement 6: IAM Roles (Least-Privilege Model)
Two distinct IAM roles are provisioned for ECS to preserve strict boundary separation:

1. **ECS Task Execution Role (`opspilot-ecs-execution-role`)**:
   - **Purpose**: Used by the AWS ECS Agent to prepare and launch container tasks.
   - **Permissions**:
     - `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage` (ECR image pulling).
     - `logs:CreateLogStream`, `logs:PutLogEvents` (Writing container startup logs).
     - `secretsmanager:GetSecretValue` on specific `arn:aws:secretsmanager:*:*:secret:/${environment}/opspilot/*` ARNs only.
     - `kms:Decrypt` on the OpsPilot KMS CMK ARN only.
   - **Boundary**: Has zero permissions to read database data, access S3 buckets, or modify infrastructure.

2. **ECS Task Role (`opspilot-ecs-task-role`)**:
   - **Purpose**: Assumed by the running OpsPilot Python application code inside the container.
   - **Permissions**:
     - `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket` strictly scoped to `arn:aws:s3:::opspilot-artifacts-${environment}-*`.
     - `cloudwatch:PutMetricData` scoped to the `OpsPilot/AIOps` namespace for emitting operational telemetry.
     - `kms:GenerateDataKey`, `kms:Decrypt` on the OpsPilot KMS CMK for object encryption.
   - **Boundary**: Has zero permission to read Secrets Manager secrets, pull ECR images, or execute administrative IAM commands.

### Requirement 7: Database Access
- **Network Isolation**: RDS PostgreSQL resides in Private Isolated Subnets with no route to an Internet Gateway or NAT Gateway. It is impossible to connect to the database directly from the public internet.
- **Security Group Chaining**: The RDS Security Group allows inbound TCP traffic on port 5432 **only** if the source is the `opspilot-ecs-tasks-sg` security group ID. No IP ranges (`0.0.0.0/0` or CIDRs) are permitted.
- **TLS Enforcement**: RDS PostgreSQL parameter group enforces SSL connections (`rds.force_ssl = 1`). Connections from the FastAPI backend require SSL mode (`sslmode=require`).
- **Connection Management**: SQLAlchemy connection pool configured with `pool_size = 5`, `max_overflow = 5`, and `pool_pre_ping = True` to verify socket liveness.
- **Administrative Access**: Direct emergency administrative access is conducted via AWS Systems Manager (SSM) Session Manager through a temporary bastion host or ECS Exec session, preventing the need for open SSH ports or public IPs.

### Requirement 8: Logging, Monitoring & Observability
- **Centralized CloudWatch Logs**:
  - Log Group `/aws/ecs/opspilot-api-${environment}`: Structured JSON logs from FastAPI and Uvicorn.
  - Log Group `/aws/ecs/opspilot-worker-${environment}`: Structured JSON logs from background telemetry workers.
  - Log Group `/aws/rds/instance/opspilot-postgres-${environment}/postgresql`: Database slow query and engine error logs.
- **Retention Policies**:
  - Development: 14 days
  - Staging: 30 days
  - Production: 90 days (with S3 archival for long-term compliance)
- **Container Insights**: Enabled on the ECS cluster to capture task-level CPU, memory, network I/O, and disk usage metrics.
- **CloudWatch Metric Alarms**:
  1. `OpsPilot-API-High5xxErrors`: Triggers if HTTP 5XX error rate exceeds 1% of total requests over a 5-minute window.
  2. `OpsPilot-ECS-HighCPU`: Triggers if ECS service CPU utilization exceeds 80% for 3 consecutive 1-minute evaluations.
  3. `OpsPilot-ECS-HighMemory`: Triggers if ECS memory utilization exceeds 85%.
  4. `OpsPilot-RDS-HighCPU`: Triggers if RDS instance CPU exceeds 80%.
  5. `OpsPilot-RDS-LowStorage`: Triggers if free database storage space drops below 5 GB.
  6. `OpsPilot-Worker-Unhealthy`: Triggers if the background worker heartbeat fails or task crashes.
- **Notification**: Alarms publish to an Amazon SNS topic (`opspilot-alerts-${environment}`) routed to SRE on-call Slack channels and PagerDuty endpoints.
- **Unified CloudWatch Dashboard**: Real-time widgets visualizing API throughput, 5xx/4xx error rates, p95 latency, worker task iterations, and RDS connections.

---

## 5. Multi-Environment Configuration Matrix

The deployment supports three distinct environment profiles:

| Dimension | Development (`dev.tfvars`) | Staging (`staging.tfvars`) | Production (`prod.tfvars`) |
| :--- | :--- | :--- | :--- |
| **VPC CIDR** | `10.10.0.0/16` | `10.20.0.0/16` | `10.30.0.0/16` |
| **Availability Zones** | 2 | 2 | 3 |
| **NAT Gateways** | 1 (Shared across AZs) | 1 (Shared across AZs) | 2 or 3 (One per AZ for HA) |
| **ECS Task CPU / RAM** | 256 vCPU / 512 MB | 512 vCPU / 1024 MB | 1024 vCPU / 2048 MB |
| **ECS Desired Count (API)** | 1 | 2 | 2 (Autoscaling up to 8) |
| **ECS Capacity Provider** | Fargate Spot (70% savings) | Fargate | Fargate |
| **RDS Instance Class** | `db.t4g.micro` | `db.t4g.small` | `db.t4g.medium` or `db.m6g.large` |
| **RDS Multi-AZ** | No (Single-AZ) | No | Yes (Synchronous Standby) |
| **RDS Backup Retention** | 7 days | 14 days | 30 days |
| **RDS Deletion Protection** | True | True | True |
| **ElastiCache Redis Class** | `cache.t4g.micro` (Single node) | `cache.t4g.micro` | `cache.t4g.small` (Multi-AZ Replica) |
| **CloudWatch Log Retention** | 14 days | 30 days | 90 days |
| **CloudFront WAF** | Disabled | Optional | Enabled (AWS Managed Common Rules) |

---

## 6. Protection Against Automatic Destruction

To ensure zero accidental data loss or outages:
1. **Terraform Lifecycle Rules**: Critical resources (RDS Database, S3 Buckets, KMS Keys, Secrets) include `lifecycle { prevent_destroy = true }` in production configurations.
2. **RDS Deletion Protection**: `deletion_protection = true` is set on the RDS instance, preventing deletion via AWS Console, CLI, or Terraform without explicit out-of-band administrative override.
3. **S3 Object Versioning & MFA Delete**: Artifact and state buckets preserve all previous object versions. Deletions create delete markers rather than permanently purging data.
4. **State Lock Protection**: Remote Terraform state uses Amazon S3 with an Amazon DynamoDB lock table (`opspilot-terraform-locks`) to prevent concurrent modifications or destructive race conditions.

---

## 7. Deployment & Rollback Runbooks

### 7.1 Automated CI/CD Deployment Flow
1. **Build & Test**: Continuous Integration executes unit and integration tests (`pytest`, `npm test`).
2. **Container Image Build & Push**:
   - Builds backend Docker image and tags with Git commit SHA: `${ECR_REPO_API}:${GITHUB_SHA}`.
   - Pushes image to Amazon ECR.
3. **Frontend Build & Deployment**:
   - Builds production Vite SPA with `VITE_API_BASE_URL=""` (relative path proxied by CloudFront).
   - Syncs static assets to S3: `aws s3 sync dist/ s3://${FRONTEND_BUCKET}/ --delete`.
   - Creates CloudFront cache invalidation: `aws cloudfront create-invalidation --distribution-id ${DIST_ID} --paths "/*"`.
4. **Database Migrations**:
   - Runs Alembic / SQLAlchemy schema migration task via standalone ECS task definition before updating running services.
5. **ECS Rolling Deployment**:
   - Updates ECS service task definition with the new ECR image tag.
   - Amazon ECS provisions new tasks, verifies target group health checks on `/api/v1/health`, and gradually shifts traffic.
   - Upon healthy confirmation, old tasks receive `SIGTERM` and drain connections.

### 7.2 Zero-Downtime Rollback Strategy
If an incident or regression occurs after deployment:

#### Frontend Rollback:
```bash
# 1. Rollback S3 static assets to previous Git commit artifacts
aws s3 sync ./backup-dist/ s3://${FRONTEND_BUCKET}/ --delete

# 2. Invalidate CloudFront edge cache immediately
aws cloudfront create-invalidation \
  --distribution-id ${DIST_ID} \
  --paths "/*"
```

#### Backend API & Worker Rollback:
```bash
# 1. Roll back ECS service to previous known-stable Task Definition revision
PREVIOUS_REVISION=$(aws ecs describe-task-definition \
  --task-definition opspilot-api-${ENVIRONMENT} \
  --query "taskDefinition.revision" --output text)
ROLLBACK_REVISION=$((PREVIOUS_REVISION - 1))

aws ecs update-service \
  --cluster opspilot-cluster-${ENVIRONMENT} \
  --service opspilot-api-${ENVIRONMENT} \
  --task-definition opspilot-api-${ENVIRONMENT}:${ROLLBACK_REVISION} \
  --force-new-deployment

aws ecs update-service \
  --cluster opspilot-cluster-${ENVIRONMENT} \
  --service opspilot-worker-${ENVIRONMENT} \
  --task-definition opspilot-worker-${ENVIRONMENT}:${ROLLBACK_REVISION} \
  --force-new-deployment
```

#### Database Rollback:
- If a schema migration is backwards-incompatible:
  - Restore database to point-in-time recovery timestamp prior to deployment using RDS automated snapshots:
    ```bash
    aws rds restore-db-instance-to-point-in-time \
      --source-db-instance-identifier opspilot-postgres-${ENVIRONMENT} \
      --target-db-instance-identifier opspilot-postgres-restored \
      --restore-time "2026-09-29T14:00:00Z"
    ```
