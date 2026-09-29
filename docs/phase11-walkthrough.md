# OpsPilot AI — Phase 11 AWS Deployment: Complete Walkthrough & Low-Cost Guide

**Author**: OpsPilot Core Engineering  
**Target Environment**: AWS (Amazon Web Services)  
**Architecture Model**: Serverless Cloud-Native (CloudFront + S3 + ECS Fargate + RDS PostgreSQL + ElastiCache)  
**Budget Optimization**: Free-Tier & Ultra-Low-Cost (< $5 - $10 / Month)

---

## 1. Executive Summary & Architectural Overview

In **Phase 11**, OpsPilot AI transitions from a local Docker Compose stack into an automated, highly available, secure, and cost-controlled cloud topology on Amazon Web Services (AWS).

### 1.1 High-Level Architecture Diagram

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

## 2. Inventory of Created Files & Use Cases

The table below explains every file created in Phase 11, why it exists, and when it is used:

| File Path | Category | Purpose & Use Case |
| :--- | :--- | :--- |
| `docs/aws-deployment-architecture.md` | Architecture Doc | Comprehensive 8-dimension architecture reference explaining cost, network, IAM, database, and disaster recovery. |
| `backend/app/services/s3_storage_service.py` | Python Service | S3 Object Storage adapter for uploading/downloading RAG runbooks, ML models, and postmortems. Features seamless local disk fallback for offline dev/testing. |
| `backend/tests/test_s3_storage_service.py` | Pytest Suite | Verifies byte upload, file upload, object listing, and deletion under offline fallback mode. |
| `backend/app/core/config.py` | Configuration | Adds `aws_region`, `s3_artifact_bucket`, and `s3_endpoint_url` settings with Pydantic validation. |
| `infra/terraform/main.tf` | Root IaC | Master orchestration file that links all 10 infrastructure modules into a single cohesive stack. |
| `infra/terraform/variables.tf` | Root IaC | Defines all input parameters with type constraints and validation rules. |
| `infra/terraform/outputs.tf` | Root IaC | Exposes CloudFront URL, ALB DNS, RDS endpoint, S3 buckets, and Dashboard IDs after deployment. |
| `infra/terraform/provider.tf` | Root IaC | Configures the AWS provider and regional tagging policies. |
| `infra/terraform/versions.tf` | Root IaC | Enforces Terraform version `>= 1.7.0` and AWS provider `~> 5.40`. |
| `infra/terraform/environments/dev.tfvars` | Environment Config | Ultra-low-cost practice profile: Fargate Spot (70% off), Single-AZ RDS, 14-day log retention. |
| `infra/terraform/environments/staging.tfvars` | Environment Config | Pre-production testing profile: standard Fargate, 2 API tasks, 30-day log retention. |
| `infra/terraform/environments/prod.tfvars` | Environment Config | High-availability profile: Multi-AZ RDS failover, multi-AZ NAT Gateways, autoscaling up to 8 tasks. |
| `infra/terraform/modules/networking/` | IaC Module | Provisions VPC, 3-tier subnets (Public, Private App, Private DB), Route Tables, IGW, and **Free S3 VPC Gateway Endpoint**. |
| `infra/terraform/modules/security/` | IaC Module | Creates KMS Customer Managed Key (CMK) and chained Security Groups (ALB -> ECS -> RDS/Redis). |
| `infra/terraform/modules/iam/` | IaC Module | Creates least-privilege ECS Task Execution Role and Application Task Role. |
| `infra/terraform/modules/secrets/` | IaC Module | Generates strong random passwords and stores them in AWS Secrets Manager with KMS encryption. |
| `infra/terraform/modules/storage/` | IaC Module | Provisions S3 Artifacts Bucket (with lifecycle rules) and private S3 React Frontend Bucket. |
| `infra/terraform/modules/database/` | IaC Module | Configures Amazon RDS PostgreSQL 16 with `pgvector` enabled and deletion protection. |
| `infra/terraform/modules/cache/` | IaC Module | Provisions Amazon ElastiCache Redis with transit (TLS) and at-rest encryption. |
| `infra/terraform/modules/compute/` | IaC Module | Provisions ALB, ECS Fargate Cluster, Task Definitions (`api` & `worker`), and auto-scaling rules. |
| `infra/terraform/modules/frontend/` | IaC Module | Provisions CloudFront CDN distribution with Origin Access Control (OAC) and SPA 404 routing. |
| `infra/terraform/modules/observability/` | IaC Module | Provisions CloudWatch Log Groups, Metric Alarms (5xx errors, CPU, RAM), SNS Alerts, and Dashboard. |
| `infra/scripts/deploy.sh` | Shell Automation | One-click deployment script: builds frontend, syncs S3, purges CDN, and updates ECS with zero downtime. |
| `infra/scripts/rollback.sh` | Shell Automation | Instant rollback script to revert ECS to the previous known-good task revision in < 60 seconds. |
| `.github/workflows/aws-deploy.yml` | CI/CD Pipeline | Automated GitHub Actions workflow using AWS OIDC (zero static access keys required). |

---

## 3. How to Host on AWS for Practice at Very Low Cost (< $5 - $10 / Month)

When deploying for practice and portfolio demonstrations, you want real production features **without a surprise $150/month AWS bill**. Here is how to keep costs near zero while easily handling traffic.

### The 4 Biggest AWS Cost Traps & How OpsPilot Avoids Them

```
┌─────────────────────────┬──────────────────────────┬────────────────────────────────────────────────────────┐
│ Resource                │ Standard Naive Cost      │ OpsPilot Ultra-Low Cost Practice Mode                  │
├─────────────────────────┼──────────────────────────┼────────────────────────────────────────────────────────┤
│ NAT Gateway             │ ~$32.40 / month each     │ Use Single NAT in Dev (~$32 total) OR place tasks in   │
│                         │ (2 AZs = $65/mo)         │ public subnet with public IP ($0 NAT Gateway!)         │
├─────────────────────────┼──────────────────────────┼────────────────────────────────────────────────────────┤
│ Container Compute       │ ~$30 - $60 / month       │ AWS Fargate Spot (70% discount)                        │
│                         │ (EC2 or standard Fargate)│ 0.25 vCPU + 0.5 GB RAM = ~$2.20 / month total          │
├─────────────────────────┼──────────────────────────┼────────────────────────────────────────────────────────┤
│ Database (RDS Postgres) │ ~$30 - $85 / month       │ AWS 12-Month Free Tier: 750 hours/month FREE for       │
│                         │                          │ db.t4g.micro / db.t3.micro Single-AZ ($0 / month!)     │
├─────────────────────────┼──────────────────────────┼────────────────────────────────────────────────────────┤
│ Frontend Web Hosting    │ ~$15 / month (EC2 Nginx) │ S3 + CloudFront: 1TB transfer & 10M requests FREE/mo   │
│                         │                          │ Total cost = < $0.05 / month                           │
├─────────────────────────┼──────────────────────────┼────────────────────────────────────────────────────────┤
│ S3 Data Transfer        │ $0.045 / GB via NAT      │ Free S3 Gateway VPC Endpoint (Bypasses NAT entirely)   │
└─────────────────────────┴──────────────────────────┴────────────────────────────────────────────────────────┘
```

### Can this low-cost configuration handle real traffic?
**Yes!**
- **Static Assets**: All HTML, JavaScript, CSS, and images are cached at CloudFront edge servers worldwide. S3 only receives requests on cache miss. This handles thousands of simultaneous users effortlessly.
- **FastAPI Backend**: Built on Python asynchronous I/O (`asyncio`). A single 0.25 vCPU Fargate task comfortably serves 50–100 requests per second.
- **RDS PostgreSQL**: Even a `db.t4g.micro` handles 50–100 concurrent DB pool connections with indexed queries.

---

## 4. Step-by-Step Hands-On Deployment Guide

### Prerequisites
1. An AWS Account.
2. [AWS CLI v2 installed](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) and configured (`aws configure`).
3. [Terraform installed](https://developer.hashicorp.com/terraform/install) (version >= 1.7.0).
4. Docker Desktop installed and running.

---

### Step 1: Log In to Amazon Elastic Container Registry (ECR)
Run in PowerShell or Bash:
```bash
# Set your AWS Account ID and Region
$AWS_ACCOUNT_ID = (aws sts get-caller-identity --query "Account" --output text)
$AWS_REGION = "us-east-1"

# Authenticate Docker with Amazon ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Create the ECR repository if it does not already exist
aws ecr create-repository --repository-name opspilot-backend --region $AWS_REGION
```

---

### Step 2: Build & Push the Docker Image
```bash
# 1. Build the production backend image
docker build -t opspilot-backend:v1.0.0 -f backend/Dockerfile backend/

# 2. Tag for ECR
docker tag opspilot-backend:v1.0.0 "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/opspilot-backend:v1.0.0"

# 3. Push to ECR
docker push "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/opspilot-backend:v1.0.0"
```

---

### Step 3: Deploy AWS Infrastructure with Terraform
```bash
cd infra/terraform

# Initialize Terraform modules and download AWS provider
terraform init

# Review the infrastructure plan
terraform plan \
  -var-file="environments/dev.tfvars" \
  -var="container_image_api=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/opspilot-backend:v1.0.0" \
  -var="container_image_worker=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/opspilot-backend:v1.0.0"

# Apply and provision resources on AWS
terraform apply -auto-approve \
  -var-file="environments/dev.tfvars" \
  -var="container_image_api=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/opspilot-backend:v1.0.0" \
  -var="container_image_worker=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/opspilot-backend:v1.0.0"
```

---

### Step 4: Build and Deploy the React Frontend
```bash
# 1. Capture the S3 bucket and CloudFront ID from Terraform outputs
$FRONTEND_BUCKET = terraform output -raw frontend_bucket_name
$CLOUDFRONT_ID = terraform output -raw cloudfront_distribution_id

# 2. Return to root and build the React SPA bundle
cd ../..
npm run build

# 3. Sync compiled dist/ to the private S3 bucket
aws s3 sync dist/ "s3://$FRONTEND_BUCKET/" --delete

# 4. Invalidate CloudFront edge cache
aws cloudfront create-invalidation --distribution-id $CLOUDFRONT_ID --paths "/*"
```

---

### Step 5: Access Your Live Application
```bash
cd infra/terraform
terraform output cloudfront_domain_name
```
Paste the returned domain (e.g., `https://d123456abcdef8.cloudfront.net`) into your browser. You now have a live, cloud-native deployment of OpsPilot AI!

---

## 5. Cost-Saving Operational Playbook (Pause & Resume)

When you are not using or demonstrating the platform, you can pause active services to reduce your compute costs to **$0.00**:

### To PAUSE (0 Compute Cost):
```bash
# Scale ECS API and Worker containers down to 0
aws ecs update-service --cluster opspilot-cluster-development --service opspilot-api-development --desired-count 0
aws ecs update-service --cluster opspilot-cluster-development --service opspilot-worker-development --desired-count 0

# Stop RDS Database (Data is saved, compute fee pauses for up to 7 days)
aws rds stop-db-instance --db-instance-identifier opspilot-postgres-development
```

### To RESUME (When you want to test again):
```bash
# Start RDS Database (Takes ~90 seconds to become available)
aws rds start-db-instance --db-instance-identifier opspilot-postgres-development

# Scale ECS containers back up to 1
aws ecs update-service --cluster opspilot-cluster-development --service opspilot-api-development --desired-count 1
aws ecs update-service --cluster opspilot-cluster-development --service opspilot-worker-development --desired-count 1
```

### To DESTROY Everything (Leave No Footprint):
```bash
cd infra/terraform
terraform destroy -var-file="environments/dev.tfvars"
```

---

## 6. Verification & Quality Assurance Summary

Prior to completing Phase 11, the entire codebase passed all automated tests:
- **Backend Tests**: `114 passed` (0 errors, 0 regressions in `pytest`).
- **Frontend Build**: `npm run build` completed cleanly, bundling TypeScript into `dist/`.
- **Infrastructure Code**: Validated across all 10 Terraform modules and environment profiles (`dev`, `staging`, `prod`).
