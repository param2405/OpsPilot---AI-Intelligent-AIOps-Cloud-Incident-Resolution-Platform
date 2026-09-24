# Architecture Specification: Kong API Gateway & Ingress Traffic Routing

## Architectural Role & Network Perimeter
The Kong API Gateway acts as the unified reverse proxy, ingress router, and security perimeter for all external and intra-service traffic across the OpsPilot cluster.

## Route Topology & Upstream Definitions
The gateway routes incoming HTTP/HTTPS traffic to internal microservices based on URI prefixes:
- `/api/v1/auth` -> `identity-service:8080`
- `/api/v1/incidents` -> `incident-service:8000`
- `/api/v1/ml` -> `ml-inference-service:8000`
- `/api/v1/rag` -> `rag-service:8000`
- `/api/v1/telemetry` -> `telemetry-ingestion:9000`

## Security & Authentication Policies
1. TLS Termination: TLS 1.3 enforced with automated Let's Encrypt wildcard certificate renewals via Cert-Manager.
2. JWT Verification: Kong JWT plugin inspects the `Authorization: Bearer <token>` header. Public keys are retrieved from the internal JWKS endpoint with 15-minute key rotation caching.
3. IP Allowlisting & Rate Limiting:
   - Global rate limit: 10,000 requests per minute per IP using Redis cluster token-bucket state.
   - Tenant-level rate limit: 5,000 requests per minute per authenticated API key.

## Health Probes & Passive Circuit Breaking
Kong executes active and passive health checks against all upstream endpoints:
- Active Health Checks: HTTP GET `/health/ready` every 5 seconds. Upstream target is marked unhealthy after 3 consecutive non-200 responses.
- Passive Circuit Breakers: If 5 consecutive HTTP 5xx responses occur within 10 seconds, Kong temporarily routes traffic away from the offending pod for 30 seconds before re-evaluating.
