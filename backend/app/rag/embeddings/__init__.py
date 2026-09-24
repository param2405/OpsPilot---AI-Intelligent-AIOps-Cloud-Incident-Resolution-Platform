"""Reusable semantic embedding service and runbook index for future RAG."""

from app.rag.embeddings.sample_runbooks import CANONICAL_RUNBOOKS
from app.rag.embeddings.service import LogSemanticEmbeddingService

__all__ = [
    "CANONICAL_RUNBOOKS",
    "LogSemanticEmbeddingService",
]
