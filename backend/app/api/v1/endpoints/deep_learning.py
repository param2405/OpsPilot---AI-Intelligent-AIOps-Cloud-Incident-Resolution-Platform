"""FastAPI endpoints for Deep Learning Log Sequence Analysis and Semantic Search."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.ml.deep_learning.inference.inference_engine import LogSequenceInferenceEngine
from app.ml.deep_learning.preprocessing.log_tokenizer import LogTemplateMiner, LogVocabulary
from app.models.incident import Incident
from app.rag.embeddings.service import LogSemanticEmbeddingService
from app.schemas.deep_learning import (
    DLModelInfoResponse,
    LogSequencePredictRequest,
    LogSequencePredictResponse,
    SemanticSearchHit,
    SemanticSearchRequest,
    SemanticSearchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml/dl", tags=["Deep Learning Log Analysis"])

# Module-level singletons for inference and embeddings
_INFERENCE_ENGINE: Optional[LogSequenceInferenceEngine] = None
_EMBEDDING_SERVICE: Optional[LogSemanticEmbeddingService] = None


def get_inference_engine() -> LogSequenceInferenceEngine:
    """Retrieve or initialize cached inference engine singleton."""
    global _INFERENCE_ENGINE
    if _INFERENCE_ENGINE is not None:
        return _INFERENCE_ENGINE

    checkpoint_path = "ml_models/log_sequence/champion_model.pt"
    vocab_path = "ml_models/log_sequence/vocab.json"
    miner_path = "ml_models/log_sequence/miner.json"

    vocab = LogVocabulary.load(vocab_path) if os.path.exists(vocab_path) else LogVocabulary()
    miner = None
    if os.path.exists(miner_path):
        with open(miner_path, "r", encoding="utf-8") as f:
            miner = LogTemplateMiner.from_dict(json.load(f))

    if os.path.exists(checkpoint_path):
        engine = LogSequenceInferenceEngine(
            vocab=vocab,
            miner=miner,
            checkpoint_path=checkpoint_path,
        )
    else:
        # Fallback to untrained template-aware engine if checkpoint not yet generated
        engine = LogSequenceInferenceEngine(vocab=vocab, miner=miner)

    _INFERENCE_ENGINE = engine
    return _INFERENCE_ENGINE


def get_embedding_service() -> LogSemanticEmbeddingService:
    """Retrieve or initialize semantic embedding service singleton."""
    global _EMBEDDING_SERVICE
    if _EMBEDDING_SERVICE is None:
        _EMBEDDING_SERVICE = LogSemanticEmbeddingService()
    return _EMBEDDING_SERVICE


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post(
    "/predict-sequence",
    response_model=LogSequencePredictResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict anomaly on a temporal log sequence",
)
def predict_log_sequence(
    request: LogSequencePredictRequest,
    engine: LogSequenceInferenceEngine = Depends(get_inference_engine),
) -> LogSequencePredictResponse:
    """Evaluate a chronological sequence of raw log messages with PyTorch LSTM/GRU.
    
    Returns anomaly probability, binary classification, and self-attention attribution
    pinpointing which exact log event triggered the anomaly.
    """
    try:
        prediction = engine.predict(
            messages=request.messages,
            service_id=request.service_id,
            threshold=request.threshold,
        )
        return LogSequencePredictResponse(**prediction)
    except Exception as exc:
        logger.exception("Sequence prediction failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Log sequence prediction failed: {str(exc)}",
        )


@router.post(
    "/semantic-search",
    response_model=SemanticSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search runbooks and incidents by semantic similarity",
)
def semantic_search(
    request: SemanticSearchRequest,
    embedder: LogSemanticEmbeddingService = Depends(get_embedding_service),
    db: Session = Depends(get_db),
) -> SemanticSearchResponse:
    """Find the most relevant engineering runbooks and historical incident postmortems
    semantically matching incoming error logs or symptoms.
    """
    start_time = time.perf_counter()
    corpus_items: List[Dict[str, Any]] = []

    # 1. Include Runbooks if requested
    if request.corpus_type in ("runbooks", "both"):
        runbook_hits = embedder.search_runbooks(request.query, top_k=request.top_k)
        for rb in runbook_hits:
            corpus_items.append({
                "id": rb.get("id", "RB-UNKNOWN"),
                "title": rb.get("title", ""),
                "failure_domain": rb.get("failure_domain"),
                "similarity_score": rb.get("similarity_score", 0.0),
                "rank": rb.get("rank", 0),
                "content": rb.get("symptoms"),
                "steps": rb.get("steps"),
                "tags": rb.get("tags"),
            })

    # 2. Include Historical Incidents from DB if requested
    if request.corpus_type in ("incidents", "both"):
        try:
            incidents = db.scalars(select(Incident)).all()
            inc_dicts = [
                {
                    "id": inc.id,
                    "title": inc.title,
                    "failure_domain": inc.incident_type,
                    "symptoms": inc.symptoms,
                    "resolution": inc.resolution,
                    "steps": [inc.resolution],
                    "tags": [inc.severity, inc.service_id],
                }
                for inc in incidents
            ]
            inc_hits = embedder.find_top_k_similar(
                query=request.query,
                corpus=inc_dicts,
                text_field="symptoms",
                top_k=request.top_k,
            )
            for inc in inc_hits:
                corpus_items.append({
                    "id": inc.get("id", "INC-UNKNOWN"),
                    "title": inc.get("title", ""),
                    "failure_domain": inc.get("failure_domain"),
                    "similarity_score": inc.get("similarity_score", 0.0),
                    "rank": inc.get("rank", 0),
                    "content": inc.get("symptoms"),
                    "steps": inc.get("steps"),
                    "tags": inc.get("tags"),
                })
        except Exception as exc:
            logger.warning("Could not query DB incidents for semantic search: %s", exc)

    # Sort combined results descending by similarity score
    corpus_items.sort(key=lambda x: x["similarity_score"], reverse=True)
    top_results = corpus_items[: request.top_k]

    # Re-assign ranks 1..K
    hits = []
    for rank, item in enumerate(top_results, start=1):
        item["rank"] = rank
        hits.append(SemanticSearchHit(**item))

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return SemanticSearchResponse(
        query=request.query,
        total_results=len(hits),
        results=hits,
        latency_ms=elapsed_ms,
    )


@router.get(
    "/model-info",
    response_model=DLModelInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active deep learning model metadata and benchmark",
)
def get_model_info() -> DLModelInfoResponse:
    """Retrieve metadata, benchmark metrics, and architecture info for active deep learning models."""
    manifest_path = "ml_models/log_sequence/manifest.json"
    if not os.path.exists(manifest_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deep learning model manifest not found. Please train models first.",
        )

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["device"] = "cpu"
    return DLModelInfoResponse(**data)
