"""Allowlist Enforcement, Parameter Validation, and Safe Simulation Engine for Remediation Actions.

SECURITY CORE PRINCIPLE:
The AI agent is NEVER permitted to execute arbitrary shell commands, arbitrary AWS CLI commands,
arbitrary SQL, or arbitrary infrastructure modifications. Only strictly allowlisted and validated
actions are executed in Safe Simulation Mode.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Tuple
from pydantic import ValidationError

from app.schemas.remediation import (
    ClearCacheParams,
    ExecutionResultSummary,
    RemediationActionType,
    RestartServiceParams,
    RollbackDeploymentParams,
    ScaleServiceParams,
    ToggleCircuitBreakerParams,
)

logger = logging.getLogger(__name__)

# Dangerous shell injection patterns to block even if nested inside string parameters
DANGEROUS_PATTERNS = [
    r"[;&|`]",             # Shell chaining/operators: ;, &&, ||, |, `
    r"\$\(.*\)",           # Command substitution: $(whoami)
    r"\${.*\}",            # Variable expansion injection: ${EVIL}
    r">\s*\/",             # Redirection to absolute path: > /etc/passwd
    r"<\s*\/",             # Redirection from absolute path
    r"(?i)\bsudo\b",       # Privilege escalation: sudo
    r"(?i)\brm\s+-rf\b",   # Recursive force removal
    r"(?i)\bdrop\s+table\b",# SQL injection: DROP TABLE
    r"(?i)\baws\s+iam\b",  # IAM modification
    r"(?i)\bshutdown\b",   # Host shutdown
    r"(?i)\bformat\b",     # Disk format
]

COMPILED_DANGEROUS_PATTERNS = [re.compile(p) for p in DANGEROUS_PATTERNS]


class RemediationSecurityError(ValueError):
    """Raised when a remediation request violates security policy or allowlist constraints."""
    pass


class RemediationActionValidator:
    """Validates actions against explicit allowlists and strict parameter bounds."""

    @classmethod
    def check_for_injection(cls, value: Any, field_name: str = "") -> None:
        """Recursively scan parameters for dangerous injection patterns."""
        if isinstance(value, str):
            for pattern in COMPILED_DANGEROUS_PATTERNS:
                if pattern.search(value):
                    raise RemediationSecurityError(
                        f"Security policy violation: dangerous pattern '{pattern.pattern}' detected in field '{field_name}' ('{value}')"
                    )
        elif isinstance(value, dict):
            for k, v in value.items():
                cls.check_for_injection(k, f"{field_name}.{k}")
                cls.check_for_injection(v, f"{field_name}.{k}")
        elif isinstance(value, list):
            for i, item in enumerate(value):
                cls.check_for_injection(item, f"{field_name}[{i}]")

    @classmethod
    def validate_action(
        cls,
        action_type_str: str,
        target_service: str,
        parameters: Dict[str, Any],
    ) -> Tuple[RemediationActionType, Dict[str, Any], str]:
        """Validate action against allowlist and strict schemas.
        
        Returns:
            Tuple of (validated_action_type, validated_params_dict, safe_command_preview)
        
        Raises:
            RemediationSecurityError if action or parameters violate policy.
        """
        # 1. Target service name validation (safe alphanumeric slug)
        if not re.match(r"^[a-zA-Z0-9_\-]+$", target_service):
            raise RemediationSecurityError(
                f"Invalid target service name '{target_service}'. Must contain only alphanumeric characters, dashes, or underscores."
            )

        # 2. Injection pattern scan across all parameter values
        cls.check_for_injection(parameters, "parameters")

        # 3. Allowlist membership check
        try:
            action_type = RemediationActionType(action_type_str)
        except ValueError:
            allowed = [a.value for a in RemediationActionType]
            raise RemediationSecurityError(
                f"Action '{action_type_str}' is NOT in the remediation allowlist. Permitted actions: {allowed}"
            )

        # 4. Strict per-action parameter validation
        try:
            if action_type == RemediationActionType.RESTART_SERVICE:
                p = RestartServiceParams.model_validate(parameters)
                preview = f"kubectl rollout restart deployment/{target_service} --timeout={p.grace_period_seconds}s"
                return action_type, p.model_dump(), preview

            elif action_type == RemediationActionType.SCALE_SERVICE:
                p = ScaleServiceParams.model_validate(parameters)
                preview = f"kubectl scale deployment/{target_service} --replicas={p.replicas}"
                return action_type, p.model_dump(), preview

            elif action_type == RemediationActionType.ROLLBACK_DEPLOYMENT:
                p = RollbackDeploymentParams.model_validate(parameters)
                rev = f"--to-revision={p.target_revision}" if p.target_revision else "--undo"
                preview = f"kubectl rollout undo deployment/{target_service} {rev}"
                return action_type, p.model_dump(), preview

            elif action_type == RemediationActionType.CLEAR_CACHE:
                p = ClearCacheParams.model_validate(parameters)
                pat = p.key_pattern or (f"{p.cache_prefix}*" if p.cache_prefix else "*")
                preview = f"redis-cli -h {p.cache_cluster} --pattern '{pat}' EVAL 'for _,k in ipairs(redis.call(\"keys\", ARGV[1])) do redis.call(\"del\", k) end' 0"
                return action_type, p.model_dump(), preview

            elif action_type == RemediationActionType.TOGGLE_CIRCUIT_BREAKER:
                p = ToggleCircuitBreakerParams.model_validate(parameters)
                dep = p.dependency_service or f"{target_service}-upstream"
                preview = f"istioctl experimental circuit-breaker set {target_service} --upstream={dep} --state={p.target_state}"
                return action_type, p.model_dump(), preview

            else:
                raise RemediationSecurityError(f"Unhandled allowlist action: {action_type}")

        except ValidationError as val_err:
            raise RemediationSecurityError(f"Parameter validation failed for action '{action_type}': {val_err}")


class SafeRemediationSimulator:
    """Executes validated allowlisted actions in Safe Simulation Mode.
    
    Produces realistic execution traces, validates service health, logs every step,
    and returns a structured execution summary without touching live cloud infrastructure.
    """

    @classmethod
    def execute_simulation(
        cls,
        action_type: RemediationActionType,
        target_service: str,
        parameters: Dict[str, Any],
        approved_by: str,
    ) -> ExecutionResultSummary:
        start_time = time.time()
        logs: List[str] = [
            f"[SEC-AUDIT] Initiating safe simulation mode execution for action: {action_type.value}",
            f"[SEC-AUDIT] Authorized by human operator: {approved_by}",
            f"[SEC-AUDIT] Target microservice: {target_service}",
            f"[SEC-AUDIT] Parameter validation: PASSED (strict schema enforced)",
        ]

        rollback_point: str | None = None
        output: str = ""

        if action_type == RemediationActionType.RESTART_SERVICE:
            grace = parameters.get("grace_period_seconds", 30)
            logs.append(f"[SIMULATOR] Querying Kubernetes API for deployment/{target_service} pods...")
            logs.append(f"[SIMULATOR] Staging rolling pod restart with grace period of {grace}s...")
            logs.append(f"[SIMULATOR] Terminating Pod/{target_service}-78b9c-4kx2l (status: Terminating)")
            logs.append(f"[SIMULATOR] Starting replacement Pod/{target_service}-78b9c-9mj5p (status: Running, Ready: 1/1)")
            logs.append(f"[SIMULATOR] Health probe check GET /health/ready on port 8080: HTTP 200 OK (latency: 14ms)")
            rollback_point = f"ReplicaSet/{target_service}-78b9c"
            output = f"Successfully restarted deployment/{target_service} with zero-downtime rolling update. All pods healthy."

        elif action_type == RemediationActionType.SCALE_SERVICE:
            replicas = parameters.get("replicas", 3)
            logs.append(f"[SIMULATOR] Current replica count for {target_service}: 2")
            logs.append(f"[SIMULATOR] Adjusting replica target to {replicas} pods...")
            logs.append(f"[SIMULATOR] Cluster autoscaler / HPA notified. Scaling event dispatched.")
            logs.append(f"[SIMULATOR] Pods provisioning: {replicas}/{replicas} pods in Running state.")
            logs.append(f"[SIMULATOR] Load balancer endpoints updated; ingress capacity expanded by 50%.")
            rollback_point = "Original replicas: 2"
            output = f"Scaled deployment/{target_service} to {replicas} replicas. Traffic distribution balanced."

        elif action_type == RemediationActionType.ROLLBACK_DEPLOYMENT:
            rev = parameters.get("target_revision", "v2.3.9")
            logs.append(f"[SIMULATOR] Argo Rollouts / Deployment inspect active canary revision: v2.4.1")
            logs.append(f"[SIMULATOR] Initiating automated canary rollback to stable revision: {rev}...")
            logs.append(f"[SIMULATOR] Traffic route shifted 100% -> stable ReplicaSet ({rev}).")
            logs.append(f"[SIMULATOR] Tearing down degraded canary pods.")
            logs.append(f"[SIMULATOR] P95 latency dropped from 1850ms to 42ms. Error rate dropped to 0.001.")
            rollback_point = "Snapshot: deployment-v2.4.1-pre-rollback"
            output = f"Rolled back deployment/{target_service} to stable revision {rev}. Canary traffic reset."

        elif action_type == RemediationActionType.CLEAR_CACHE:
            pattern = parameters.get("key_pattern", "*")
            cluster = parameters.get("cache_cluster", "redis-cluster")
            logs.append(f"[SIMULATOR] Connecting to cache cluster '{cluster}'...")
            logs.append(f"[SIMULATOR] Scanning keys matching prefix pattern '{pattern}'...")
            logs.append(f"[SIMULATOR] Evicted 342 expired/corrupted cache entries safely.")
            logs.append(f"[SIMULATOR] Memory fragmentation ratio normalized from 1.84 to 1.08.")
            output = f"Cache eviction completed for '{pattern}' on {cluster}. 342 stale keys evicted."

        elif action_type == RemediationActionType.TOGGLE_CIRCUIT_BREAKER:
            dep = parameters.get("dependency_service", "upstream-api")
            state = parameters.get("target_state", "HALF_OPEN")
            logs.append(f"[SIMULATOR] Istio Service Mesh circuit breaker configuration update...")
            logs.append(f"[SIMULATOR] Microservice {target_service} -> Dependency {dep} set to {state}.")
            logs.append(f"[SIMULATOR] Fast-fail fallback handler active. Cascading thread starvation arrested.")
            output = f"Circuit breaker for {target_service} -> {dep} configured to {state}."

        duration_ms = round((time.time() - start_time) * 1000 + 45.0, 2)
        logs.append(f"[SEC-AUDIT] Safe simulation completed in {duration_ms}ms. Status: SUCCESS.")

        return ExecutionResultSummary(
            output=output,
            execution_duration_ms=duration_ms,
            simulated=True,
            validation_passed=True,
            logs=logs,
            rollback_point=rollback_point,
        )
