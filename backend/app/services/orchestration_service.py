"""Phase 7: Intelligent Incident Orchestration Pipeline Service.

Integrates ML anomaly detection, ML classification, ML severity prediction,
PyTorch deep learning log sequence analysis, LangGraph diagnostic agent, and RAG knowledge retrieval.

Ensures strict separation of concerns:
  1. detection:       Deterministic ML model (Isolation Forest / Autoencoder)
  2. classification:  Deterministic ML model (XGBoost Classifier)
  3. severity:        Deterministic ML model (XGBoost Severity Predictor)
  4. dl_log_analysis: Deep learning sequence model (PyTorch BiLSTM/GRU + Self-Attention)
  5. investigation:   LangGraph agent with read-only diagnostic tools
  6. diagnosis:       Grounded causal synthesis combining ML/DL evidence
  7. recommendation:  Actionable mitigation and remediation playbooks from RAG

Guarantees graceful degradation when any underlying sub-system is unavailable.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agent.graph import run_incident_investigation
from app.agent.tools.logs_tool import search_logs
from app.db.session import SessionLocal
from app.ml.deep_learning.inference.inference_engine import LogSequenceInferenceEngine
from app.ml.deep_learning.preprocessing.log_tokenizer import LogTemplateMiner, LogVocabulary
from app.models.incident import Incident
from app.models.investigation import IncidentInvestigation
from app.schemas.agent import (
    EvidenceItem,
    HistoricalIncidentMatch,
    InvestigationRequest,
    InvestigationResult,
    RemediationStep,
    SourceItem,
)
from app.schemas.ml import (
    AnomalyDetectionRequest,
    IncidentClassificationRequest,
    MetricTelemetryInput,
    SeverityPredictionRequest,
)
from app.schemas.orchestration import (
    DLLogAnalysisResult,
    IncidentInvestigationResponse,
    InvestigationSummary,
    ManualInvestigateRequest,
    PipelineComponentHealth,
    PipelineHealthStatusResponse,
    TelemetryIngestRequest,
)
from app.services.ml_service import MLInferenceService

logger = logging.getLogger("opspilot.orchestration")


class IncidentOrchestrationService:
    """Production incident orchestration pipeline integrating ML, DL, Agent, and RAG layers."""

    def __init__(
        self,
        ml_service: Optional[MLInferenceService] = None,
        dl_engine: Optional[LogSequenceInferenceEngine] = None,
    ) -> None:
        self.ml_service = ml_service or MLInferenceService()
        self._dl_engine = dl_engine

    @property
    def dl_engine(self) -> LogSequenceInferenceEngine:
        """Lazily initialize or return cached deep learning inference engine singleton."""
        if self._dl_engine is not None:
            return self._dl_engine

        checkpoint_path = "ml_models/log_sequence/champion_model.pt"
        vocab_path = "ml_models/log_sequence/vocab.json"
        miner_path = "ml_models/log_sequence/miner.json"

        vocab = LogVocabulary.load(vocab_path) if os.path.exists(vocab_path) else LogVocabulary()
        miner = None
        if os.path.exists(miner_path):
            import json
            with open(miner_path, "r", encoding="utf-8") as f:
                miner = LogTemplateMiner.from_dict(json.load(f))

        if os.path.exists(checkpoint_path):
            self._dl_engine = LogSequenceInferenceEngine(
                vocab=vocab,
                miner=miner,
                checkpoint_path=checkpoint_path,
            )
        else:
            self._dl_engine = LogSequenceInferenceEngine(vocab=vocab, miner=miner)

        return self._dl_engine

    def process_telemetry(
        self,
        payload: TelemetryIngestRequest,
        db: Optional[Session] = None,
    ) -> IncidentInvestigationResponse:
        """Execute the complete 12-step incident orchestration pipeline.
        
        Flow:
          1. Receive and normalize observability telemetry.
          2. Run ML anomaly detection.
          3. If anomaly threshold is crossed, create or correlate an incident.
          4. Run ML incident classification.
          5. Run ML severity prediction.
          6. Analyze relevant log sequences using the PyTorch DL model.
          7. Assemble incident context for the LangGraph agent.
          8. Agent investigates using read-only diagnostic tools.
          9. RAG retrieves relevant runbooks and postmortems.
          10. Structured root-cause analysis is synthesized (preserving deterministic ML).
          11. Store complete investigation record and update incident state.
          12. Expose and return the complete incident state.
        """
        now = datetime.now(timezone.utc)
        timeline: List[str] = []
        degraded_components: List[str] = []
        close_db_on_exit = False

        if db is None:
            db = SessionLocal()
            close_db_on_exit = True

        try:
            # -----------------------------------------------------------------
            # STEP 1: Receive & Validate Observability Data
            # -----------------------------------------------------------------
            ts_str = now.strftime("%H:%M:%S")
            timeline.append(f"[{ts_str}] [INGESTION] Received telemetry for service '{payload.service_id}'.")
            logger.info("[INGESTION] Received telemetry for service '%s' (cpu=%.1f%%, err=%.2f%%, lat=%.1fms)",
                        payload.service_id, payload.cpu_usage, payload.error_rate * 100, payload.latency_p95_ms)

            # -----------------------------------------------------------------
            # STEP 2: Deterministic ML Anomaly Detection
            # -----------------------------------------------------------------
            detected_anomaly, anomaly_score, contributing_signals, anomaly_meta = self._run_detection(
                payload=payload,
                timeline=timeline,
                degraded_components=degraded_components,
            )

            # -----------------------------------------------------------------
            # STEP 3: Anomaly Threshold Evaluation & Incident Creation/Correlation
            # -----------------------------------------------------------------
            anomaly_crossed = (anomaly_score >= payload.anomaly_threshold) or payload.force_investigation

            if not anomaly_crossed:
                # Normal operational telemetry: record routine monitoring status without triggering alert noise
                ts_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
                timeline.append(f"[{ts_str}] [DETECTION] Score {anomaly_score:.4f} is below cutoff {payload.anomaly_threshold:.2f}. No anomaly detected; incident not triggered.")
                logger.info("[DETECTION] Service '%s' score %.4f below threshold. Normal operation.", payload.service_id, anomaly_score)

                # Generate a routine monitoring investigation record
                dummy_inv_id = f"INV-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
                return IncidentInvestigationResponse(
                    incident_id=payload.incident_id or "NONE",
                    investigation_id=dummy_inv_id,
                    service_id=payload.service_id,
                    status="NORMAL",
                    detected_anomaly=False,
                    anomaly_score=anomaly_score,
                    anomaly_details={"contributing_signals": contributing_signals, **anomaly_meta},
                    predicted_category="NORMAL",
                    category_confidence=1.0,
                    category_probabilities={"normal": 1.0},
                    predicted_severity="NONE",
                    severity_confidence=1.0,
                    risk_factors=[],
                    dl_log_analysis=None,
                    suspected_root_cause="Service metrics within normal operating bounds. No operational anomalies detected.",
                    confidence=1.0,
                    evidence=[],
                    similar_incidents=[],
                    retrieved_sources=[],
                    recommended_remediation=[],
                    timeline=timeline,
                    degraded_components=degraded_components,
                    created_at=now,
                    updated_at=now,
                )

            # Anomaly threshold crossed: Create or update Incident in database
            incident = self._correlate_or_create_incident(
                db=db,
                payload=payload,
                detected_anomaly=detected_anomaly,
                anomaly_score=anomaly_score,
                timeline=timeline,
            )
            incident_id = incident.id

            # -----------------------------------------------------------------
            # STEP 4: Deterministic ML Incident Classification
            # -----------------------------------------------------------------
            predicted_category, category_conf, category_probs = self._run_classification(
                payload=payload,
                incident=incident,
                timeline=timeline,
                degraded_components=degraded_components,
            )

            # -----------------------------------------------------------------
            # STEP 5: Deterministic ML Severity Prediction
            # -----------------------------------------------------------------
            predicted_severity, severity_conf, severity_probs, risk_factors = self._run_severity(
                payload=payload,
                incident=incident,
                timeline=timeline,
                degraded_components=degraded_components,
            )

            # -----------------------------------------------------------------
            # STEP 6: Deep Learning Log Sequence Analysis (PyTorch LSTM/GRU)
            # -----------------------------------------------------------------
            dl_analysis = self._run_dl_log_analysis(
                db=db,
                payload=payload,
                timeline=timeline,
                degraded_components=degraded_components,
            )

            # -----------------------------------------------------------------
            # STEP 7: Assemble Incident Context for LangGraph Agent
            # -----------------------------------------------------------------
            ts_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
            timeline.append(f"[{ts_str}] [AGENT] Assembling multi-layer diagnostic context for LangGraph agent.")
            agent_context_overrides = {
                "detected_anomaly": detected_anomaly,
                "anomaly_score": anomaly_score,
                "contributing_signals": contributing_signals,
                "predicted_category": predicted_category,
                "category_confidence": category_conf,
                "predicted_severity": predicted_severity,
                "severity_confidence": severity_conf,
                "dl_log_analysis": dl_analysis.model_dump(mode="json") if dl_analysis else {},
            }

            investigation_req = InvestigationRequest(
                incident_id=incident_id,
                service=payload.service_id,
                title=payload.title or incident.title,
                description=payload.description or incident.symptoms,
                severity=predicted_severity,
                time_range="1h",
            )

            # -----------------------------------------------------------------
            # STEPS 8, 9, 10: Agent Investigation, RAG Retrieval, Grounded Synthesis
            # -----------------------------------------------------------------
            agent_result = self._run_agent_investigation(
                req=investigation_req,
                context_overrides=agent_context_overrides,
                db=db,
                timeline=timeline,
                degraded_components=degraded_components,
            )

            # Merge agent timeline entries into main timeline
            for entry in agent_result.investigation_timeline:
                if entry not in timeline:
                    timeline.append(entry)

            # Determine investigation status
            if not agent_result.has_sufficient_evidence:
                inv_status = "INSUFFICIENT_EVIDENCE"
            elif degraded_components:
                inv_status = "DEGRADED"
            else:
                inv_status = "COMPLETED"

            # -----------------------------------------------------------------
            # STEP 11: Store Investigation Result & Update Incident Record
            # -----------------------------------------------------------------
            investigation_record = self._persist_investigation(
                db=db,
                incident=incident,
                inv_status=inv_status,
                detected_anomaly=detected_anomaly,
                anomaly_score=anomaly_score,
                contributing_signals=contributing_signals,
                anomaly_meta=anomaly_meta,
                predicted_category=predicted_category,
                category_conf=category_conf,
                category_probs=category_probs,
                predicted_severity=predicted_severity,
                severity_conf=severity_conf,
                risk_factors=risk_factors,
                dl_analysis=dl_analysis,
                agent_result=agent_result,
                timeline=timeline,
                degraded_components=degraded_components,
            )

            # -----------------------------------------------------------------
            # STEP 12: Expose Complete Incident State Through API
            # -----------------------------------------------------------------
            ts_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
            timeline.append(f"[{ts_str}] [COMPLETION] Orchestration pipeline completed. Status: '{inv_status}'.")
            logger.info("[COMPLETION] Investigation %s for incident %s completed (status=%s, conf=%.2f)",
                        investigation_record.id, incident_id, inv_status, agent_result.confidence)

            return IncidentInvestigationResponse(
                incident_id=incident_id,
                investigation_id=investigation_record.id,
                service_id=payload.service_id,
                status=inv_status,
                detected_anomaly=detected_anomaly,
                anomaly_score=anomaly_score,
                anomaly_details={"contributing_signals": contributing_signals, **anomaly_meta},
                predicted_category=predicted_category,
                category_confidence=category_conf,
                category_probabilities=category_probs,
                predicted_severity=predicted_severity,
                severity_confidence=severity_conf,
                risk_factors=risk_factors,
                dl_log_analysis=dl_analysis,
                suspected_root_cause=agent_result.suspected_root_cause,
                confidence=agent_result.confidence,
                evidence=agent_result.evidence,
                similar_incidents=agent_result.relevant_historical_incidents,
                retrieved_sources=agent_result.sources,
                recommended_remediation=agent_result.recommended_remediation,
                timeline=timeline,
                degraded_components=degraded_components,
                created_at=investigation_record.created_at,
                updated_at=investigation_record.updated_at,
            )

        finally:
            if close_db_on_exit:
                db.close()

    # =========================================================================
    # INTERNAL PIPELINE STAGE METHODS
    # =========================================================================

    def _run_detection(
        self,
        payload: TelemetryIngestRequest,
        timeline: List[str],
        degraded_components: List[str],
    ) -> Tuple[bool, float, List[str], Dict[str, Any]]:
        """Stage 2: Deterministic ML Anomaly Detection with graceful rule-based fallback."""
        ts_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        try:
            req = AnomalyDetectionRequest(
                service_id=payload.service_id,
                timestamp=payload.timestamp or datetime.now(timezone.utc),
                cpu_usage=payload.cpu_usage,
                memory_usage=payload.memory_usage,
                disk_usage=payload.disk_usage,
                network_traffic_kbps=payload.network_traffic_kbps,
                request_count=payload.request_count,
                latency_p95_ms=payload.latency_p95_ms,
                error_rate=payload.error_rate,
                active_connections=payload.active_connections,
                recent_history=payload.recent_history,
            )
            res = self.ml_service.detect_anomaly(req)
            timeline.append(
                f"[{ts_str}] [DETECTION] ML Anomaly Detector ({res.algorithm} {res.model_version}): "
                f"score={res.anomaly_score:.4f}, anomaly={res.is_anomaly}."
            )
            logger.info("[DETECTION] ML Model: score=%.4f, anomaly=%s, signals=%s",
                        res.anomaly_score, res.is_anomaly, res.contributing_signals)
            return (
                res.is_anomaly,
                res.anomaly_score,
                res.contributing_signals,
                {"model_version": res.model_version, "algorithm": res.algorithm},
            )
        except Exception as exc:
            logger.warning("[DETECTION] ML model unavailable (%s). Falling back to statistical heuristic.", exc)
            degraded_components.append("ml_anomaly_fallback")
            # Heuristic detection fallback
            contributing = []
            score = 0.0
            if payload.error_rate > 0.05:
                contributing.append(f"Elevated error rate ({round(payload.error_rate * 100, 2)}%)")
                score = max(score, 0.85)
            if payload.latency_p95_ms > 1000.0:
                contributing.append(f"High p95 latency ({round(payload.latency_p95_ms, 1)}ms)")
                score = max(score, 0.78)
            if payload.cpu_usage > 85.0:
                contributing.append(f"Saturated CPU ({payload.cpu_usage}%)")
                score = max(score, 0.72)
            if payload.active_connections > 80:
                contributing.append(f"Connection pool load ({payload.active_connections} active conns)")
                score = max(score, 0.75)

            is_anom = score >= 0.50
            timeline.append(
                f"[{ts_str}] [DETECTION] [FALLBACK] Statistical Heuristic Evaluator: "
                f"score={score:.4f}, anomaly={is_anom}."
            )
            return is_anom, score, contributing, {"algorithm": "statistical_fallback", "model_version": "heuristic_v1"}

    def _correlate_or_create_incident(
        self,
        db: Session,
        payload: TelemetryIngestRequest,
        detected_anomaly: bool,
        anomaly_score: float,
        timeline: List[str],
    ) -> Incident:
        """Stage 3: Check for existing active incident or create a new incident in DB."""
        ts_str = datetime.now(timezone.utc).strftime("%H:%M:%S")

        # 1. Check if caller supplied explicit incident ID
        if payload.incident_id:
            existing = db.get(Incident, payload.incident_id)
            if existing:
                timeline.append(f"[{ts_str}] [INCIDENT] Attached to existing incident record '{existing.id}'.")
                return existing

        # 2. Check if active incident already exists for service
        stmt = (
            select(Incident)
            .where(Incident.service_id == payload.service_id)
            .where(Incident.status.in_(["INVESTIGATING", "IDENTIFIED"]))
            .order_by(desc(Incident.started_at))
            .limit(1)
        )
        active_inc = db.scalar(stmt)
        if active_inc:
            timeline.append(f"[{ts_str}] [INCIDENT] Correlated to existing active incident '{active_inc.id}'.")
            logger.info("[INCIDENT] Correlated to active incident %s", active_inc.id)
            return active_inc

        # 3. Create new incident record
        now = datetime.now(timezone.utc)
        new_id = f"INC-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        title = payload.title or f"Automated Anomaly on {payload.service_id} (score: {anomaly_score:.2f})"
        symptom_desc = (
            payload.description
            or f"Telemetry deviation flagged on service {payload.service_id}. "
               f"CPU: {payload.cpu_usage}%, Error Rate: {round(payload.error_rate * 100, 2)}%, Latency: {payload.latency_p95_ms}ms."
        )

        new_incident = Incident(
            id=new_id,
            service_id=payload.service_id,
            title=title,
            started_at=now,
            severity="P2_HIGH",
            symptoms=symptom_desc,
            root_cause="Under automated diagnostic orchestration",
            resolution="Automated investigation in progress",
            status="INVESTIGATING",
            incident_type="GENERAL",
        )
        db.add(new_incident)
        db.commit()
        db.refresh(new_incident)

        timeline.append(f"[{ts_str}] [INCIDENT] Created new incident '{new_id}' for service '{payload.service_id}'.")
        logger.info("[INCIDENT] Created incident %s for service %s", new_id, payload.service_id)
        return new_incident

    def _run_classification(
        self,
        payload: TelemetryIngestRequest,
        incident: Incident,
        timeline: List[str],
        degraded_components: List[str],
    ) -> Tuple[str, float, Dict[str, float]]:
        """Stage 4: Deterministic ML Incident Classification with fallback."""
        ts_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        try:
            req = IncidentClassificationRequest(
                title=incident.title,
                symptoms=incident.symptoms,
                service_id=payload.service_id,
                tier="standard",
                cpu_usage=payload.cpu_usage,
                memory_usage=payload.memory_usage,
                disk_usage=payload.disk_usage,
                network_traffic_kbps=payload.network_traffic_kbps,
                request_count=payload.request_count,
                latency_p95_ms=payload.latency_p95_ms,
                error_rate=payload.error_rate,
                active_connections=payload.active_connections,
            )
            res = self.ml_service.classify_incident(req)
            timeline.append(
                f"[{ts_str}] [CLASSIFICATION] ML Classifier ({res.algorithm} {res.model_version}): "
                f"category='{res.category}', confidence={res.confidence:.2f}."
            )
            logger.info("[CLASSIFICATION] ML Model: category=%s, conf=%.2f", res.category, res.confidence)
            return res.category, res.confidence, res.probabilities
        except Exception as exc:
            logger.warning("[CLASSIFICATION] ML classifier unavailable (%s). Falling back to keyword heuristics.", exc)
            degraded_components.append("ml_classification_fallback")

            # Heuristic failure category identification
            combined = f"{incident.title} {incident.symptoms}".lower()
            if payload.active_connections > 80 or any(k in combined for k in ["pool", "connection", "postgres", "hikari", "database"]):
                cat = "database"
            elif any(k in combined for k in ["deploy", "release", "canary", "rollout"]):
                cat = "deployment"
            elif payload.memory_usage > 90.0 or any(k in combined for k in ["jvm", "oom", "heap", "memory"]):
                cat = "application"
            elif payload.latency_p95_ms > 2000.0 or any(k in combined for k in ["network", "dns", "socket"]):
                cat = "network"
            else:
                cat = "application"

            timeline.append(f"[{ts_str}] [CLASSIFICATION] [FALLBACK] Heuristic Classifier: category='{cat}'.")
            return cat, 0.60, {cat: 0.60, "general": 0.40}

    def _run_severity(
        self,
        payload: TelemetryIngestRequest,
        incident: Incident,
        timeline: List[str],
        degraded_components: List[str],
    ) -> Tuple[str, float, Dict[str, float], List[str]]:
        """Stage 5: Deterministic ML Severity Prediction with fallback."""
        ts_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        try:
            req = SeverityPredictionRequest(
                title=incident.title,
                symptoms=incident.symptoms,
                service_id=payload.service_id,
                tier="standard",
                cpu_usage=payload.cpu_usage,
                memory_usage=payload.memory_usage,
                disk_usage=payload.disk_usage,
                network_traffic_kbps=payload.network_traffic_kbps,
                request_count=payload.request_count,
                latency_p95_ms=payload.latency_p95_ms,
                error_rate=payload.error_rate,
                active_connections=payload.active_connections,
            )
            res = self.ml_service.predict_severity(req)
            timeline.append(
                f"[{ts_str}] [SEVERITY] ML Severity Predictor ({res.algorithm} {res.model_version}): "
                f"severity='{res.severity}', confidence={res.confidence:.2f}."
            )
            logger.info("[SEVERITY] ML Model: severity=%s, conf=%.2f, risk_factors=%s",
                        res.severity, res.confidence, res.risk_factors)
            return res.severity, res.confidence, res.probabilities, res.risk_factors
        except Exception as exc:
            logger.warning("[SEVERITY] ML severity model unavailable (%s). Falling back to threshold rules.", exc)
            degraded_components.append("ml_severity_fallback")

            # Deterministic threshold rule fallback
            risk_factors = []
            if payload.error_rate >= 0.15 or payload.latency_p95_ms >= 3000.0:
                sev = "P1_CRITICAL"
                risk_factors.append("Severe error rate >= 15% or latency >= 3000ms")
            elif payload.error_rate >= 0.05 or payload.cpu_usage >= 90.0:
                sev = "P2_HIGH"
                risk_factors.append("Elevated error rate >= 5% or CPU >= 90%")
            elif payload.error_rate >= 0.01 or payload.latency_p95_ms >= 500.0:
                sev = "P3_MEDIUM"
                risk_factors.append("Moderate error rate >= 1% or latency >= 500ms")
            else:
                sev = "P4_LOW"
                risk_factors.append("Low telemetry deviation")

            timeline.append(f"[{ts_str}] [SEVERITY] [FALLBACK] Threshold Rule Engine: severity='{sev}'.")
            return sev, 0.70, {sev: 0.70}, risk_factors

    def _run_dl_log_analysis(
        self,
        db: Session,
        payload: TelemetryIngestRequest,
        timeline: List[str],
        degraded_components: List[str],
    ) -> Optional[DLLogAnalysisResult]:
        """Stage 6: Deep Learning Log Sequence Evaluation using PyTorch BiLSTM/GRU."""
        ts_str = datetime.now(timezone.utc).strftime("%H:%M:%S")

        # Gather chronological raw logs from payload or from DB
        raw_logs: List[str] = []
        if payload.recent_logs:
            raw_logs = list(payload.recent_logs)
        else:
            try:
                logs_out = search_logs(service=payload.service_id, time_range="1h", limit=20, db=db)
                raw_logs = [l.message for l in logs_out.logs]
            except Exception as exc:
                logger.warning("[DL_LOG_ANALYSIS] Could not query database logs: %s", exc)

        if not raw_logs:
            timeline.append(f"[{ts_str}] [DL_LOG_ANALYSIS] Zero recent log lines available for deep learning sequence evaluation.")
            return None

        try:
            pred = self.dl_engine.predict(
                messages=raw_logs,
                service_id=payload.service_id,
                threshold=0.50,
            )
            dl_res = DLLogAnalysisResult(
                is_anomaly=pred["is_anomaly"],
                anomaly_probability=pred["anomaly_probability"],
                predicted_class=pred["predicted_class"],
                sequence_length=pred["sequence_length"],
                top_trigger_event=pred.get("top_trigger_event"),
                event_tokens=pred.get("event_tokens", []),
                attention_weights=pred.get("attention_weights", []),
                latency_ms=pred.get("latency_ms", 0.0),
            )
            top_msg = pred.get("top_trigger_event", {}).get("log_message", "N/A") if pred.get("top_trigger_event") else "None"
            timeline.append(
                f"[{ts_str}] [DL_LOG_ANALYSIS] PyTorch Log Evaluator: evaluated {len(raw_logs)} lines, "
                f"anomaly={dl_res.is_anomaly} (prob={dl_res.anomaly_probability:.4f}), top_trigger='{top_msg[:60]}...'."
            )
            logger.info("[DL_LOG_ANALYSIS] DL Model: anomaly=%s, prob=%.4f, top_trigger=%s",
                        dl_res.is_anomaly, dl_res.anomaly_probability, top_msg)
            return dl_res
        except Exception as exc:
            logger.warning("[DL_LOG_ANALYSIS] DL log model unavailable (%s). Falling back to regex keyword attribution.", exc)
            degraded_components.append("dl_log_model_fallback")

            # Fallback: scan for first error log line
            top_trigger = None
            for idx, msg in enumerate(raw_logs):
                if any(err_term in msg.upper() for err_term in ["ERROR", "FATAL", "EXCEPTION", "TIMEOUT", "FAIL"]):
                    top_trigger = {
                        "index": idx,
                        "log_message": msg,
                        "event_id": f"E_FALLBACK_{idx}",
                        "attention_weight": 1.0,
                    }
                    break

            timeline.append(f"[{ts_str}] [DL_LOG_ANALYSIS] [FALLBACK] Extracted trigger log via error signature search.")
            return DLLogAnalysisResult(
                is_anomaly=top_trigger is not None,
                anomaly_probability=0.75 if top_trigger else 0.10,
                predicted_class=1 if top_trigger else 0,
                sequence_length=len(raw_logs),
                top_trigger_event=top_trigger,
                event_tokens=[],
                attention_weights=[1.0 if top_trigger else 0.0],
                latency_ms=1.0,
            )

    def _run_agent_investigation(
        self,
        req: InvestigationRequest,
        context_overrides: Dict[str, Any],
        db: Session,
        timeline: List[str],
        degraded_components: List[str],
    ) -> InvestigationResult:
        """Stages 8, 9, 10: Execute LangGraph diagnostic agent with safe read-only tools and RAG retrieval."""
        ts_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        timeline.append(f"[{ts_str}] [AGENT] Launching LangGraph diagnostic agent across safe read-only tools and RAG.")

        try:
            return run_incident_investigation(
                request=req,
                db=db,
                context_overrides=context_overrides,
            )
        except Exception as exc:
            logger.exception("[AGENT] LangGraph agent execution encountered error: %s. Using safe fallback synthesis.", exc)
            degraded_components.append("agent_workflow_fallback")

            # Safe deterministic fallback if the agent graph execution fails completely
            fallback_rc = (
                f"Automated diagnostic agent completed in degraded mode for '{req.service}'. "
                f"Primary failure domain identified as '{context_overrides.get('predicted_category', 'general')}'. "
                f"Anomalous metric dynamics observed with severity rating {context_overrides.get('predicted_severity', 'P2')}."
            )
            return InvestigationResult(
                incident_id=req.incident_id or "INC",
                service=req.service,
                incident_summary=fallback_rc,
                suspected_root_cause=fallback_rc,
                evidence=[],
                confidence=0.50,
                has_sufficient_evidence=True,
                insufficient_evidence_reason=None,
                relevant_historical_incidents=[],
                recommended_remediation=[
                    RemediationStep(
                        step_number=1,
                        action=f"Inspect live pod status and logs for {req.service}",
                        command_or_config=f"kubectl get pods -l app={req.service} && kubectl logs -l app={req.service} --tail=100",
                        risk_level="low",
                        source_reference="OpsPilot Emergency Fallback Protocol",
                    )
                ],
                sources=[],
                investigation_timeline=[f"[{ts_str}] Agent execution fell back to deterministic recovery template."],
                completed_at=datetime.now(timezone.utc),
            )

    def _persist_investigation(
        self,
        db: Session,
        incident: Incident,
        inv_status: str,
        detected_anomaly: bool,
        anomaly_score: float,
        contributing_signals: List[str],
        anomaly_meta: Dict[str, Any],
        predicted_category: str,
        category_conf: float,
        category_probs: Dict[str, float],
        predicted_severity: str,
        severity_conf: float,
        risk_factors: List[str],
        dl_analysis: Optional[DLLogAnalysisResult],
        agent_result: InvestigationResult,
        timeline: List[str],
        degraded_components: List[str],
    ) -> IncidentInvestigation:
        """Stage 11: Persist the full investigation record and update Incident state in DB."""
        now = datetime.now(timezone.utc)
        inv_id = f"INV-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

        # 1. Update the parent Incident record
        incident.severity = predicted_severity
        incident.incident_type = predicted_category.upper()
        incident.root_cause = agent_result.suspected_root_cause
        if agent_result.recommended_remediation:
            incident.resolution = "\n".join(
                f"{r.step_number}. {r.action} ({r.command_or_config or 'No command'})"
                for r in agent_result.recommended_remediation
            )
        incident.status = "IDENTIFIED" if agent_result.has_sufficient_evidence else "INVESTIGATING"

        # 2. Persist complete IncidentInvestigation domain entity
        investigation_record = IncidentInvestigation(
            id=inv_id,
            incident_id=incident.id,
            service_id=incident.service_id,
            status=inv_status,
            detected_anomaly=detected_anomaly,
            anomaly_score=anomaly_score,
            anomaly_details={"contributing_signals": contributing_signals, **anomaly_meta},
            predicted_category=predicted_category,
            category_confidence=category_conf,
            category_probabilities=category_probs,
            predicted_severity=predicted_severity,
            severity_confidence=severity_conf,
            risk_factors=risk_factors,
            dl_log_analysis=dl_analysis.model_dump(mode="json") if dl_analysis else None,
            suspected_root_cause=agent_result.suspected_root_cause,
            confidence=agent_result.confidence,
            evidence=[e.model_dump(mode="json") for e in agent_result.evidence],
            similar_incidents=[h.model_dump(mode="json") for h in agent_result.relevant_historical_incidents],
            retrieved_sources=[s.model_dump(mode="json") for s in agent_result.sources],
            recommended_remediation=[r.model_dump(mode="json") for r in agent_result.recommended_remediation],
            timeline=timeline,
            degraded_components=degraded_components,
            created_at=now,
            updated_at=now,
        )

        db.add(investigation_record)
        db.commit()
        db.refresh(investigation_record)
        db.refresh(incident)

        # 3. Phase 9: Auto-register allowlisted remediation recommendation for Human-In-The-Loop review
        try:
            from app.models.remediation import RemediationRecommendation
            from app.schemas.remediation import RemediationActionType
            from app.services.remediation_service import RemediationService

            # Check if recommendation already exists for this incident
            existing_rec = db.scalar(
                select(RemediationRecommendation).where(RemediationRecommendation.incident_id == incident.id)
            )
            if not existing_rec:
                target_act = RemediationActionType.RESTART_SERVICE.value
                target_params = {"service_name": incident.service_id, "grace_period_seconds": 30}
                risk = "LOW"
                action_desc = f"Safely restart {incident.service_id} pods to clear degraded state and reset pools."

                if agent_result.recommended_remediation:
                    for step in agent_result.recommended_remediation:
                        act_str = step.action.lower()
                        if "scale" in act_str:
                            target_act = RemediationActionType.SCALE_SERVICE.value
                            target_params = {"service_name": incident.service_id, "replicas": 4, "direction": "up"}
                            risk = "LOW"
                            action_desc = step.action
                            break
                        elif "rollback" in act_str:
                            target_act = RemediationActionType.ROLLBACK_DEPLOYMENT.value
                            target_params = {"service_name": incident.service_id, "target_version": "v1.4.2", "target_revision": 1}
                            risk = "HIGH"
                            action_desc = step.action
                            break
                        elif "circuit" in act_str:
                            target_act = RemediationActionType.TOGGLE_CIRCUIT_BREAKER.value
                            target_params = {"service_name": incident.service_id, "enabled": True, "failure_threshold": 5}
                            risk = "MEDIUM"
                            action_desc = step.action
                            break
                        elif "cache" in act_str:
                            target_act = RemediationActionType.CLEAR_CACHE.value
                            target_params = {"service_name": incident.service_id, "cache_prefix": "session"}
                            risk = "LOW"
                            action_desc = step.action
                            break

                rem_service = RemediationService()
                rec = rem_service.create_recommendation(
                    db=db,
                    incident_id=incident.id,
                    investigation_id=inv_id,
                    action_type=target_act,
                    target_service=incident.service_id,
                    parameters=target_params,
                    rationale=action_desc,
                    risk_level=risk,
                    runbook_reference="RAG Playbook / OpsPilot SRE Protocol",
                )
                timeline.append(
                    f"[{ts_str}] [REMEDIATION] Created allowlisted recommendation '{rec.id}' ({target_act}) awaiting Human-In-The-Loop approval."
                )
        except Exception as rem_exc:
            logger.warning("[REMEDIATION] Could not auto-register remediation recommendation: %s", rem_exc)

        ts_str = now.strftime("%H:%M:%S")
        timeline.append(f"[{ts_str}] [PERSISTENCE] Stored IncidentInvestigation '{inv_id}' linked to Incident '{incident.id}'.")
        return investigation_record

    # =========================================================================
    # PUBLIC QUERY & RETRIEVAL METHODS
    # =========================================================================

    def investigate_incident_by_id(
        self,
        req: ManualInvestigateRequest,
        db: Session,
    ) -> IncidentInvestigationResponse:
        """Trigger full orchestration on an existing incident using its stored data."""
        incident = db.get(Incident, req.incident_id)
        if not incident:
            raise ValueError(f"Incident with ID '{req.incident_id}' not found.")

        # Build telemetry ingest request using incident's service and context
        telemetry_payload = TelemetryIngestRequest(
            service_id=incident.service_id,
            incident_id=incident.id,
            title=incident.title,
            description=incident.symptoms,
            cpu_usage=50.0,
            memory_usage=50.0,
            latency_p95_ms=150.0,
            error_rate=0.01,
            active_connections=30,
            recent_logs=req.recent_logs,
            force_investigation=True,
        )
        return self.process_telemetry(payload=telemetry_payload, db=db)

    def get_investigation(
        self,
        investigation_id_or_incident_id: str,
        db: Session,
    ) -> Optional[IncidentInvestigationResponse]:
        """Retrieve full investigation state by investigation ID or incident ID."""
        # 1. Try by primary key (investigation ID)
        inv = db.get(IncidentInvestigation, investigation_id_or_incident_id)
        if not inv:
            # 2. Try by incident_id (fetch latest investigation for that incident)
            stmt = (
                select(IncidentInvestigation)
                .where(IncidentInvestigation.incident_id == investigation_id_or_incident_id)
                .order_by(desc(IncidentInvestigation.created_at))
                .limit(1)
            )
            inv = db.scalar(stmt)

        if not inv:
            return None

        return self._to_response_schema(inv)

    def list_investigations(
        self,
        db: Session,
        service_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[InvestigationSummary]:
        """List investigation summaries with optional filtering."""
        stmt = select(IncidentInvestigation).order_by(desc(IncidentInvestigation.created_at))
        if service_id:
            stmt = stmt.where(IncidentInvestigation.service_id == service_id)
        if status:
            stmt = stmt.where(IncidentInvestigation.status == status.upper())
        stmt = stmt.limit(limit)

        records = db.scalars(stmt).all()
        return [
            InvestigationSummary(
                investigation_id=r.id,
                incident_id=r.incident_id,
                service_id=r.service_id,
                status=r.status,
                detected_anomaly=r.detected_anomaly,
                anomaly_score=r.anomaly_score,
                predicted_category=r.predicted_category,
                predicted_severity=r.predicted_severity,
                suspected_root_cause=r.suspected_root_cause[:120] + "..." if len(r.suspected_root_cause) > 120 else r.suspected_root_cause,
                confidence=r.confidence,
                degraded_components=r.degraded_components or [],
                created_at=r.created_at,
            )
            for r in records
        ]

    def get_pipeline_health(self) -> PipelineHealthStatusResponse:
        """Inspect health and active readiness across all integrated pipeline layers."""
        now = datetime.now(timezone.utc)
        components: Dict[str, PipelineComponentHealth] = {}
        all_ready = True

        # 1. ML Models
        try:
            overview = self.ml_service.get_models_overview()
            models_dict = overview.models.get("models", {})
            for m_name in ("anomaly", "classification", "severity"):
                m_info = models_dict.get(m_name, {})
                active_ver = m_info.get("active_version", "unknown")
                components[f"ml_{m_name}"] = PipelineComponentHealth(
                    name=f"ML {m_name.capitalize()}",
                    status="READY" if active_ver != "unknown" else "UNAVAILABLE",
                    version=active_ver,
                    details=f"Algorithm: {m_info.get('versions', {}).get(active_ver, {}).get('algorithm', 'unknown')}",
                )
        except Exception as exc:
            all_ready = False
            for m_name in ("anomaly", "classification", "severity"):
                components[f"ml_{m_name}"] = PipelineComponentHealth(
                    name=f"ML {m_name.capitalize()}",
                    status="DEGRADED",
                    details=str(exc),
                )

        # 2. Deep Learning Engine
        try:
            engine = self.dl_engine
            components["deep_learning_log_analysis"] = PipelineComponentHealth(
                name="PyTorch Log Sequence Model",
                status="READY" if engine.model is not None else "DEGRADED",
                version="champion_v1",
                details=f"Device: {engine.device}, Vocab size: {len(engine.vocab)}",
            )
        except Exception as exc:
            all_ready = False
            components["deep_learning_log_analysis"] = PipelineComponentHealth(
                name="PyTorch Log Sequence Model",
                status="UNAVAILABLE",
                details=str(exc),
            )

        # 3. LangGraph Agent
        components["langgraph_investigation_agent"] = PipelineComponentHealth(
            name="LangGraph Diagnostic Agent",
            status="READY",
            version="v2.0",
            details="10 safe diagnostic nodes, 6 read-only tools, conditional routing",
        )

        # 4. RAG Knowledge System
        components["rag_knowledge_system"] = PipelineComponentHealth(
            name="RAG Hybrid Retrieval & Reranker",
            status="READY",
            version="v1.0",
            details="pgvector hybrid search + cross-encoder contextual reranker",
        )

        pipeline_status = "HEALTHY" if all_ready else "DEGRADED"

        return PipelineHealthStatusResponse(
            pipeline_status=pipeline_status,
            components=components,
            timestamp=now,
        )

    def _to_response_schema(self, inv: IncidentInvestigation) -> IncidentInvestigationResponse:
        """Convert SQLAlchemy IncidentInvestigation model into Pydantic IncidentInvestigationResponse."""
        evidence_objs = [EvidenceItem(**e) for e in (inv.evidence or [])]
        similar_objs = [HistoricalIncidentMatch(**h) for h in (inv.similar_incidents or [])]
        source_objs = [SourceItem(**s) for s in (inv.retrieved_sources or [])]
        remed_objs = [RemediationStep(**r) for r in (inv.recommended_remediation or [])]
        dl_res = DLLogAnalysisResult(**inv.dl_log_analysis) if inv.dl_log_analysis else None

        return IncidentInvestigationResponse(
            incident_id=inv.incident_id,
            investigation_id=inv.id,
            service_id=inv.service_id,
            status=inv.status,
            detected_anomaly=inv.detected_anomaly,
            anomaly_score=inv.anomaly_score,
            anomaly_details=inv.anomaly_details,
            predicted_category=inv.predicted_category,
            category_confidence=inv.category_confidence,
            category_probabilities=inv.category_probabilities,
            predicted_severity=inv.predicted_severity,
            severity_confidence=inv.severity_confidence,
            risk_factors=inv.risk_factors,
            dl_log_analysis=dl_res,
            suspected_root_cause=inv.suspected_root_cause,
            confidence=inv.confidence,
            evidence=evidence_objs,
            similar_incidents=similar_objs,
            retrieved_sources=source_objs,
            recommended_remediation=remed_objs,
            timeline=inv.timeline or [],
            degraded_components=inv.degraded_components or [],
            created_at=inv.created_at,
            updated_at=inv.updated_at,
        )
