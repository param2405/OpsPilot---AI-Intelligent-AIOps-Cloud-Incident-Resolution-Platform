"""Synthetic Observability Data Generator for OpsPilot AI.

Generates reproducible, high-fidelity time-series metrics, structured logs,
deployments, and incidents with realistic temporal dynamics, causal relationships,
and diurnal traffic patterns.
"""

from datetime import datetime, timedelta, timezone
import math
import random
from typing import Any, Dict, List, Tuple
import uuid

from sqlalchemy.orm import Session

from app.models.deployment import Deployment
from app.models.incident import Incident
from app.models.log import LogEntry
from app.models.metric import Metric
from app.models.service import Service


class SyntheticDataGenerator:
    """Deterministic synthetic data generator modeling realistic microservice telemetry."""

    SERVICES = [
        {"id": "api-gateway", "name": "API Gateway", "tier": "critical", "owner_team": "platform"},
        {"id": "auth-service", "name": "Authentication Service", "tier": "critical", "owner_team": "identity"},
        {"id": "order-service", "name": "Order Management Service", "tier": "critical", "owner_team": "checkout"},
        {"id": "payment-service", "name": "Payment Processing Service", "tier": "critical", "owner_team": "payments"},
        {"id": "inventory-service", "name": "Inventory & Catalog Service", "tier": "high", "owner_team": "catalog"},
        {"id": "notification-service", "name": "Notification & Messaging Service", "tier": "standard", "owner_team": "messaging"},
    ]

    def __init__(self, db: Session, seed: int = 42) -> None:
        self.db = db
        self.seed = seed
        self.rng = random.Random(seed)

    @staticmethod
    def _to_utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def generate(self, days: int = 7, step_minutes: int = 5) -> Dict[str, int]:
        """Generate and commit full observability dataset spanning the given days."""
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        start_time = now - timedelta(days=days)

        # 1. Ensure Services Exist
        services = self._seed_services()

        # 2. Define Incidents & Deployments with Ground-Truth Timing
        incident_definitions = self._create_incident_schedule(start_time, now)

        # 3. Seed Deployments & Incidents
        deployments, incidents = self._seed_deployments_and_incidents(incident_definitions)

        # 4. Generate Telemetry (Metrics + Logs) for each Service
        total_metrics = 0
        total_logs = 0

        # Step through time
        current_time = start_time
        time_steps: List[datetime] = []
        while current_time <= now:
            time_steps.append(current_time)
            current_time += timedelta(minutes=step_minutes)

        for svc in services:
            svc_metrics, svc_logs = self._generate_telemetry_for_service(
                svc=svc,
                time_steps=time_steps,
                incidents=incidents,
                deployments=deployments,
            )
            self.db.add_all(svc_metrics)
            self.db.add_all(svc_logs)
            self.db.commit()
            total_metrics += len(svc_metrics)
            total_logs += len(svc_logs)

        return {
            "services": len(services),
            "deployments": len(deployments),
            "incidents": len(incidents),
            "metrics": total_metrics,
            "logs": total_logs,
        }

    def _seed_services(self) -> List[Service]:
        services: List[Service] = []
        for svc_data in self.SERVICES:
            svc = self.db.get(Service, svc_data["id"])
            if not svc:
                svc = Service(
                    id=svc_data["id"],
                    name=svc_data["name"],
                    tier=svc_data["tier"],
                    owner_team=svc_data["owner_team"],
                )
                self.db.add(svc)
            services.append(svc)
        self.db.commit()
        for svc in services:
            self.db.refresh(svc)
        return services

    def _create_incident_schedule(
        self, start_time: datetime, end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Create 7 realistic incident definitions spaced across the timeline."""
        total_span = (end_time - start_time).total_seconds()
        
        # Relative points along the timeline (0.0 to 1.0)
        return [
            {
                "id": "INC-2026-001",
                "service_id": "auth-service",
                "type": "CPU_SATURATION",
                "severity": "P1_CRITICAL",
                "start_offset": total_span * 0.15,
                "duration_minutes": 65,
                "title": "Auth Service CPU Starvation in JWT Verification Loop",
                "symptoms": "Auth service CPU pegged at 99%, p95 latency spiked from 35ms to 1850ms, client token verification timeouts.",
                "root_cause": "Catastrophic backtracking in regex claims parsing under sustained concurrent token verification traffic.",
                "resolution": "Applied deterministic DFA regex parsing hotfix, restarted worker pods; CPU normalized to 28%.",
                "needs_deployment": False,
            },
            {
                "id": "INC-2026-002",
                "service_id": "order-service",
                "type": "MEMORY_LEAK",
                "severity": "P1_CRITICAL",
                "start_offset": total_span * 0.32,
                "duration_minutes": 240,  # Slow build-up
                "title": "Gradual Memory Leak Causing OOM Kill in Order Management Service",
                "symptoms": "Order service memory steadily climbed from 35% to 96% over 4 hours before container OOM terminated (exit code 137).",
                "root_cause": "Unreleased ByteBuf allocations in asynchronous order dispatch event channel.",
                "resolution": "Fixed ByteBuf reference count release in Netty channel teardown handler and tuned heap garbage collection.",
                "needs_deployment": False,
            },
            {
                "id": "INC-2026-003",
                "service_id": "payment-service",
                "type": "DB_CONNECTION_EXHAUSTION",
                "severity": "P1_CRITICAL",
                "start_offset": total_span * 0.48,
                "duration_minutes": 50,
                "title": "Payment Service HikariCP Database Connection Pool Saturation",
                "symptoms": "Payment processing error rate spiked to 78%, p95 latency jumped to 5000ms timeout, active DB connections at 100/100 limit.",
                "root_cause": "Missing transaction commit in idempotency token verification left PostgreSQL sessions in 'idle in transaction' state.",
                "resolution": "Terminated orphaned DB locks, enclosed idempotency verification in auto-closing context manager.",
                "needs_deployment": False,
            },
            {
                "id": "INC-2026-004",
                "service_id": "inventory-service",
                "type": "API_LATENCY_SPIKE",
                "severity": "P2_HIGH",
                "start_offset": total_span * 0.62,
                "duration_minutes": 75,
                "title": "Inventory Query Latency Spike Cascading to API Gateway",
                "symptoms": "Inventory p95 latency degraded from 40ms to 3200ms; API gateway queued 180 concurrent requests awaiting inventory items.",
                "root_cause": "Sequential table scan on inventory_items due to missing composite index on (warehouse_id, sku).",
                "resolution": "Created concurrent B-tree index idx_inventory_warehouse_sku; query latency dropped to 12ms.",
                "needs_deployment": False,
            },
            {
                "id": "INC-2026-005",
                "service_id": "notification-service",
                "type": "NETWORK_DEGRADATION",
                "severity": "P2_HIGH",
                "start_offset": total_span * 0.74,
                "duration_minutes": 60,
                "title": "Push Notification Network Degradation and Socket Retransmissions",
                "symptoms": "Notification service network throughput dropped by 85%, socket timeouts and TCP packet retransmissions elevated to 14.8%.",
                "root_cause": "MTU mismatch on gateway ENI caused packet fragmentation and black hole packet dropping for payloads > 1420 bytes.",
                "resolution": "Adjusted network interface MTU to 9001 bytes and restored standard TCP buffer sizes.",
                "needs_deployment": False,
            },
            {
                "id": "INC-2026-006",
                "service_id": "order-service",
                "type": "DEPLOYMENT_FAILURE",
                "severity": "P1_CRITICAL",
                "start_offset": total_span * 0.85,
                "duration_minutes": 40,
                "title": "Production Release v2.4.0 Missing Stripe Configuration Secret",
                "symptoms": "Immediately following v2.4.0 deployment, order creation error rate spiked to 45% with 500 Internal Server Error.",
                "root_cause": "Release v2.4.0 introduced dependency on missing environment variable STRIPE_WEBHOOK_SECRET_KEY.",
                "resolution": "Initiated emergency automated rollback to v2.3.9; service health restored within 15 minutes.",
                "needs_deployment": True,
            },
            {
                "id": "INC-2026-007",
                "service_id": "payment-service",
                "type": "EXTERNAL_DEPENDENCY_FAILURE",
                "severity": "P2_HIGH",
                "start_offset": total_span * 0.93,
                "duration_minutes": 45,
                "title": "Third-Party Payment Acquirer 503 Outage and Circuit Breaker Trip",
                "symptoms": "Credit card authorizations failed with 88% error rate; external provider returned HTTP 503 Service Unavailable.",
                "root_cause": "Unscheduled maintenance downtime on primary payment processor authorization gateway.",
                "resolution": "Circuit breaker automatically opened and redirected checkout transactions to backup payment acquirer.",
                "needs_deployment": False,
            },
        ]

    def _seed_deployments_and_incidents(
        self, incident_definitions: List[Dict[str, Any]]
    ) -> Tuple[List[Deployment], List[Incident]]:
        """Seed baseline and incident-related deployments, then create incident records."""
        deployments: List[Deployment] = []
        incidents: List[Incident] = []

        now = datetime.now(timezone.utc)
        baseline_time = now - timedelta(days=6)

        # Baseline deployments for all services
        for svc_data in self.SERVICES:
            dep = Deployment(
                service_id=svc_data["id"],
                version="v2.3.0",
                deployed_at=baseline_time + timedelta(hours=self.rng.randint(1, 12)),
                environment="production",
                status="SUCCESS",
                changelog=f"Routine feature release and performance improvements for {svc_data['name']}.",
            )
            self.db.add(dep)
            deployments.append(dep)
        self.db.commit()

        # Build incidents and any linked deployments
        for inc_def in incident_definitions:
            inc_start = now - timedelta(seconds=inc_def["start_offset"])
            inc_end = inc_start + timedelta(minutes=inc_def["duration_minutes"])

            linked_dep: Deployment | None = None
            if inc_def["needs_deployment"]:
                # Failed deployment that triggered the incident
                dep_fail = Deployment(
                    service_id=inc_def["service_id"],
                    version="v2.4.0",
                    deployed_at=inc_start - timedelta(minutes=3),
                    environment="production",
                    status="FAILED",
                    changelog="Added multi-currency payment checkout options and webhook event dispatchers.",
                )
                self.db.add(dep_fail)
                self.db.commit()
                self.db.refresh(dep_fail)
                deployments.append(dep_fail)
                linked_dep = dep_fail

                # Rollback deployment
                dep_rollback = Deployment(
                    service_id=inc_def["service_id"],
                    version="v2.3.9",
                    deployed_at=inc_end - timedelta(minutes=10),
                    environment="production",
                    status="ROLLED_BACK",
                    changelog="Emergency rollback to v2.3.9 to restore stable order checkout processing.",
                )
                self.db.add(dep_rollback)
                self.db.commit()
                deployments.append(dep_rollback)

            inc = Incident(
                id=inc_def["id"],
                service_id=inc_def["service_id"],
                title=inc_def["title"],
                started_at=inc_start,
                resolved_at=inc_end,
                severity=inc_def["severity"],
                symptoms=inc_def["symptoms"],
                root_cause=inc_def["root_cause"],
                resolution=inc_def["resolution"],
                status="RESOLVED",
                incident_type=inc_def["type"],
                related_deployment_id=linked_dep.id if linked_dep else None,
            )
            self.db.add(inc)
            incidents.append(inc)

        self.db.commit()
        for inc in incidents:
            self.db.refresh(inc)

        return deployments, incidents

    def _generate_telemetry_for_service(
        self,
        svc: Service,
        time_steps: List[datetime],
        incidents: List[Incident],
        deployments: List[Deployment],
    ) -> Tuple[List[Metric], List[LogEntry]]:
        """Generate time-series metrics and correlated structured logs for a single service."""
        metrics: List[Metric] = []
        logs: List[LogEntry] = []

        # Find incidents affecting this service (or upstream if api-gateway)
        svc_incidents = [inc for inc in incidents if inc.service_id == svc.id]
        
        # Also, api-gateway is affected by inventory-service latency incident
        cascading_gateway_incident = None
        if svc.id == "api-gateway":
            for inc in incidents:
                if inc.incident_type == "API_LATENCY_SPIKE":
                    cascading_gateway_incident = inc
                    break

        for ts in time_steps:
            # 1. Compute diurnal baseline
            hour = ts.hour + ts.minute / 60.0
            # Peak activity at 14:00 UTC, trough at 02:00 UTC
            diurnal_multiplier = 0.5 + 0.5 * math.sin((hour - 8.0) * math.pi / 12.0)
            diurnal_multiplier = max(0.2, min(1.0, diurnal_multiplier))

            # Service specific baseline profiles
            tier_req_base = 600 if svc.tier == "critical" else (300 if svc.tier == "high" else 150)
            req_count = int(tier_req_base * diurnal_multiplier + self.rng.gauss(0, 15))
            req_count = max(20, req_count)

            cpu = 20.0 + 15.0 * diurnal_multiplier + self.rng.gauss(0, 2.0)
            mem = 35.0 + 10.0 * diurnal_multiplier + self.rng.gauss(0, 1.0)
            disk = 42.0 + self.rng.gauss(0, 0.2)
            net_kbps = req_count * 2.8 + self.rng.gauss(0, 30.0)
            lat_p95 = 35.0 + 10.0 * diurnal_multiplier + self.rng.gauss(0, 3.0)
            err_rate = max(0.0005, min(0.005, 0.001 + self.rng.gauss(0, 0.0005)))
            active_conns = int(15 + 15 * diurnal_multiplier + self.rng.gauss(0, 2))

            # 2. Check for active incident affecting this service
            active_inc: Incident | None = None
            for inc in svc_incidents:
                inc_start = self._to_utc(inc.started_at)
                inc_end = self._to_utc(inc.resolved_at) or ts
                if inc_start <= ts <= inc_end:
                    active_inc = inc
                    break

            is_cascading = False
            if not active_inc and cascading_gateway_incident:
                gw_start = self._to_utc(cascading_gateway_incident.started_at)
                gw_end = self._to_utc(cascading_gateway_incident.resolved_at) or ts
                if gw_start <= ts <= gw_end:
                    active_inc = cascading_gateway_incident
                    is_cascading = True

            telemetry = {
                "cpu": cpu,
                "mem": mem,
                "disk": disk,
                "net_kbps": net_kbps,
                "req_count": req_count,
                "lat_p95": lat_p95,
                "err_rate": err_rate,
                "active_conns": active_conns,
            }

            # 3. Apply Incident Perturbations & Log Generation
            generated_logs = self._apply_incident_and_logs(
                svc=svc,
                ts=ts,
                active_inc=active_inc,
                is_cascading=is_cascading,
                telemetry=telemetry,
            )
            logs.extend(generated_logs)

            # Clamp metric values
            cpu_final = max(1.0, min(100.0, round(telemetry["cpu"], 2)))
            mem_final = max(1.0, min(100.0, round(telemetry["mem"], 2)))
            disk_final = max(1.0, min(100.0, round(telemetry["disk"], 2)))
            net_final = max(0.0, round(telemetry["net_kbps"], 2))
            req_final = max(0, int(telemetry["req_count"]))
            lat_final = max(1.0, round(telemetry["lat_p95"], 2))
            err_final = max(0.0, min(1.0, round(telemetry["err_rate"], 4)))
            conn_final = max(0, int(telemetry["active_conns"]))

            m = Metric(
                service_id=svc.id,
                timestamp=ts,
                cpu_usage=cpu_final,
                memory_usage=mem_final,
                disk_usage=disk_final,
                network_traffic_kbps=net_final,
                request_count=req_final,
                latency_p95_ms=lat_final,
                error_rate=err_final,
                active_connections=conn_final,
            )
            metrics.append(m)

        return metrics, logs

    def _apply_incident_and_logs(
        self,
        svc: Service,
        ts: datetime,
        active_inc: Incident | None,
        is_cascading: bool,
        telemetry: Dict[str, Any],
    ) -> List[LogEntry]:
        """Apply incident physics and emit correlated log events."""
        logs: List[LogEntry] = []

        if not active_inc:
            # Standard ambient log (low frequency sample)
            if self.rng.random() < 0.15:
                logs.append(
                    LogEntry(
                        service_id=svc.id,
                        timestamp=ts + timedelta(seconds=self.rng.randint(1, 55)),
                        log_level="INFO",
                        message=f"Health status green; active workers processing queue (svc={svc.id})",
                        trace_id=uuid.uuid4().hex[:16],
                        metadata_json={"http_status": 200, "region": "us-east-1"},
                    )
                )
            return logs

        # Calculate progress through incident [0.0 - 1.0]
        inc_start = self._to_utc(active_inc.started_at) or ts
        inc_end = self._to_utc(active_inc.resolved_at) or ts
        inc_duration = (inc_end - inc_start).total_seconds()
        elapsed = (ts - inc_start).total_seconds()
        progress = max(0.0, min(1.0, elapsed / max(1.0, inc_duration)))

        # Temporal intensity curve: ramp up, stay high, ramp down
        if progress < 0.2:
            intensity = progress / 0.2
        elif progress < 0.8:
            intensity = 1.0
        else:
            intensity = (1.0 - progress) / 0.2

        inc_type = active_inc.incident_type

        # 1. CPU SATURATION (auth-service)
        if inc_type == "CPU_SATURATION":
            telemetry["cpu"] = 30.0 + 68.0 * intensity + self.rng.gauss(0, 1.0)
            telemetry["lat_p95"] = 35.0 + 1750.0 * intensity + self.rng.gauss(0, 25.0)
            telemetry["err_rate"] = 0.001 + 0.18 * intensity
            telemetry["active_conns"] = int(20 + 60 * intensity)
            if self.rng.random() < 0.7:
                level = "ERROR" if intensity > 0.5 else "WARN"
                trace = uuid.uuid4().hex[:16]
                logs.append(
                    LogEntry(
                        service_id=svc.id,
                        timestamp=ts + timedelta(seconds=self.rng.randint(1, 45)),
                        log_level=level,
                        message="Worker thread hung in JWT regex claims verification" if intensity > 0.6 else "High CPU utilization: worker pool queue backing up",
                        trace_id=trace,
                        metadata_json={"cpu_percent": round(telemetry["cpu"], 1), "thread_id": self.rng.randint(10, 80)},
                    )
                )

        # 2. MEMORY LEAK (order-service)
        elif inc_type == "MEMORY_LEAK":
            # Slow monotonic ramp up until OOM restart near the end
            telemetry["mem"] = 35.0 + 60.0 * (elapsed / inc_duration) + self.rng.gauss(0, 0.5)
            if progress > 0.85:
                # OOM happened, process restarted
                telemetry["mem"] = 32.0
                telemetry["err_rate"] = 0.45 if progress < 0.9 else 0.005
                logs.append(
                    LogEntry(
                        service_id=svc.id,
                        timestamp=ts + timedelta(seconds=10),
                        log_level="FATAL" if progress < 0.88 else "INFO",
                        message="java.lang.OutOfMemoryError: Java heap space. Process terminating." if progress < 0.88 else "Container order-service restarted; new replica serving traffic.",
                        trace_id=uuid.uuid4().hex[:16],
                        metadata_json={"exit_code": 137, "signal": "SIGKILL"},
                    )
                )
            else:
                telemetry["lat_p95"] = 40.0 + 350.0 * (telemetry["mem"] / 100.0)
                if self.rng.random() < 0.5 and telemetry["mem"] > 75.0:
                    logs.append(
                        LogEntry(
                            service_id=svc.id,
                            timestamp=ts + timedelta(seconds=self.rng.randint(1, 50)),
                            log_level="WARN",
                            message=f"High JVM Heap utilization ({round(telemetry['mem'], 1)}%). Frequent GC pauses observed.",
                            trace_id=uuid.uuid4().hex[:16],
                            metadata_json={"gc_time_ms": self.rng.randint(800, 2400)},
                        )
                    )

        # 3. DB CONNECTION EXHAUSTION (payment-service)
        elif inc_type == "DB_CONNECTION_EXHAUSTION":
            telemetry["active_conns"] = int(25 + 75 * intensity)
            telemetry["lat_p95"] = 45.0 + 4900.0 * intensity
            telemetry["err_rate"] = 0.002 + 0.76 * intensity
            if self.rng.random() < 0.8:
                trace = uuid.uuid4().hex[:16]
                logs.append(
                    LogEntry(
                        service_id=svc.id,
                        timestamp=ts + timedelta(seconds=self.rng.randint(1, 40)),
                        log_level="ERROR",
                        message="Timeout waiting for idle database connection from pool HikariPool-1 (connectionTimeout=5000ms)",
                        trace_id=trace,
                        metadata_json={"pool": "HikariPool-1", "active": telemetry["active_conns"], "max": 100},
                    )
                )

        # 4. API LATENCY SPIKE (inventory-service & cascading to api-gateway)
        elif inc_type == "API_LATENCY_SPIKE":
            if is_cascading:  # api-gateway
                telemetry["active_conns"] = int(25 + 155 * intensity)
                telemetry["lat_p95"] = 40.0 + 3300.0 * intensity
                telemetry["err_rate"] = 0.001 + 0.12 * intensity
                if self.rng.random() < 0.6:
                    logs.append(
                        LogEntry(
                            service_id=svc.id,
                            timestamp=ts + timedelta(seconds=self.rng.randint(1, 45)),
                            log_level="ERROR" if intensity > 0.5 else "WARN",
                            message="Upstream timeout calling GET http://inventory-service/api/v1/items",
                            trace_id=uuid.uuid4().hex[:16],
                            metadata_json={"upstream_service": "inventory-service", "status_code": 504},
                        )
                    )
            else:  # inventory-service
                telemetry["lat_p95"] = 30.0 + 3150.0 * intensity
                telemetry["cpu"] = 25.0 + 35.0 * intensity
                if self.rng.random() < 0.6:
                    logs.append(
                        LogEntry(
                            service_id=svc.id,
                            timestamp=ts + timedelta(seconds=self.rng.randint(1, 45)),
                            log_level="WARN",
                            message="Slow query detected: sequential scan on table inventory_items took 2840ms",
                            trace_id=uuid.uuid4().hex[:16],
                            metadata_json={"query": "SELECT * FROM inventory_items WHERE warehouse_id = $1", "duration_ms": int(telemetry["lat_p95"])},
                        )
                    )

        # 5. NETWORK DEGRADATION (notification-service)
        elif inc_type == "NETWORK_DEGRADATION":
            telemetry["net_kbps"] = max(50.0, telemetry["net_kbps"] * (1.0 - 0.85 * intensity))
            telemetry["lat_p95"] = 30.0 + 820.0 * intensity
            telemetry["err_rate"] = 0.001 + 0.28 * intensity
            if self.rng.random() < 0.6:
                logs.append(
                    LogEntry(
                        service_id=svc.id,
                        timestamp=ts + timedelta(seconds=self.rng.randint(1, 45)),
                        log_level="WARN" if intensity < 0.5 else "ERROR",
                        message="TCP socket packet retransmission rate elevated (packet_loss=14.8%)",
                        trace_id=uuid.uuid4().hex[:16],
                        metadata_json={"retrans_rate": "14.8%", "interface": "eth0"},
                    )
                )

        # 6. DEPLOYMENT FAILURE (order-service)
        elif inc_type == "DEPLOYMENT_FAILURE":
            telemetry["err_rate"] = 0.002 + 0.44 * intensity
            telemetry["lat_p95"] = 40.0 + 120.0 * intensity
            if self.rng.random() < 0.7:
                trace = uuid.uuid4().hex[:16]
                logs.append(
                    LogEntry(
                        service_id=svc.id,
                        timestamp=ts + timedelta(seconds=self.rng.randint(1, 45)),
                        log_level="ERROR",
                        message="KeyError: 'STRIPE_WEBHOOK_SECRET_KEY' configuration parameter missing or invalid in environment",
                        trace_id=trace,
                        metadata_json={"release": "v2.4.0", "exception": "KeyError", "status_code": 500},
                    )
                )

        # 7. EXTERNAL DEPENDENCY FAILURE (payment-service)
        elif inc_type == "EXTERNAL_DEPENDENCY_FAILURE":
            telemetry["err_rate"] = 0.002 + 0.86 * intensity
            telemetry["cpu"] = 14.0  # I/O wait, low compute
            if self.rng.random() < 0.8:
                trace = uuid.uuid4().hex[:16]
                logs.append(
                    LogEntry(
                        service_id=svc.id,
                        timestamp=ts + timedelta(seconds=self.rng.randint(1, 45)),
                        log_level="ERROR",
                        message="External payment gateway returned 503 Service Unavailable: [CircuitBreaker OPEN]",
                        trace_id=trace,
                        metadata_json={"external_endpoint": "https://api.thirdparty-bank.com/v1/charges", "http_status": 503},
                    )
                )

        return logs
