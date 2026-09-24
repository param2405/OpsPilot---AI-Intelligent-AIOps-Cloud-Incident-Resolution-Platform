"""Pydantic schemas for Deep Learning Log Sequence Analysis & Semantic Search."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LogTriggerEvent(BaseModel):
    """Specific event within the sequence that received peak attention weight."""

    index: int = Field(..., description="0-indexed position within the input log sequence")
    log_message: str = Field(..., description="Original raw log text")
    event_id: str = Field(..., description="Canonical event template ID (e.g. E4)")
    attention_weight: float = Field(..., description="Normalized attention score [0.0 - 1.0]")


class LogSequencePredictRequest(BaseModel):
    """Input payload containing a temporal list of operational logs."""

    messages: List[str] = Field(
        ...,
        min_length=1,
        description="Chronological list of raw operational log lines emitted by a service",
        examples=[[
            "Active connections reached 75/100 cap on PostgreSQL pool",
            "Queries queued and timed out after 5000ms",
            "Timeout waiting for idle database connection from pool HikariPool-1 (connectionTimeout=5000ms)",
        ]],
    )
    service_id: str = Field(default="unknown", description="Identifier of the target microservice")
    threshold: float = Field(default=0.50, ge=0.0, le=1.0, description="Anomaly classification probability cutoff")


class LogSequencePredictResponse(BaseModel):
    """Inference output from PyTorch sequence model."""

    service_id: str
    is_anomaly: bool
    anomaly_probability: float
    confidence: float
    predicted_class: int
    sequence_length: int
    event_tokens: List[str]
    top_trigger_event: Optional[LogTriggerEvent] = None
    attention_weights: List[float]
    latency_ms: float


class SemanticSearchRequest(BaseModel):
    """Input payload for semantic similarity retrieval over runbooks and historical incidents."""

    query: str = Field(
        ...,
        min_length=3,
        description="Query text, symptom description, or raw log message",
        examples=["HikariCP connection pool timeout waiting for connection"],
    )
    corpus_type: str = Field(
        default="runbooks",
        description="Target repository to search: 'runbooks', 'incidents', or 'both'",
    )
    top_k: int = Field(default=3, ge=1, le=10, description="Maximum number of relevant items to return")


class SemanticSearchHit(BaseModel):
    """Individual retrieved document or incident ranked by cosine similarity."""

    id: str
    title: str
    failure_domain: Optional[str] = None
    similarity_score: float
    rank: int
    content: Optional[str] = None
    steps: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class SemanticSearchResponse(BaseModel):
    """Retrieval response ranked by semantic cosine similarity."""

    query: str
    total_results: int
    results: List[SemanticSearchHit]
    latency_ms: float


class DLModelInfoResponse(BaseModel):
    """Manifest metadata describing active deep learning sequence models."""

    champion_architecture: str
    vocab_size: int
    window_size: int
    stride: int
    results: Dict[str, Any]
    timestamp: str
    device: str
