"""Hybrid retrieval combining dense semantic vector search and lexical search with Reciprocal Rank Fusion."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.rag import RAGChunk
from app.rag.embeddings.service import LogSemanticEmbeddingService
from app.rag.retrieval.vector_store import PostgresVectorStore

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A chunk retrieved from the hybrid search pipeline with relevance metrics."""

    chunk: RAGChunk
    score: float
    dense_score: Optional[float] = None
    lexical_score: Optional[float] = None
    dense_rank: Optional[int] = None
    lexical_rank: Optional[int] = None
    rrf_score: float = 0.0

    @property
    def id(self) -> str:
        return self.chunk.id

    @property
    def document_id(self) -> str:
        return self.chunk.document_id

    @property
    def content(self) -> str:
        return self.chunk.content

    @property
    def section(self) -> str:
        return self.chunk.section

    @property
    def service(self) -> str:
        return self.chunk.service

    @property
    def document_type(self) -> str:
        return self.chunk.document_type

    @property
    def source(self) -> str:
        return self.chunk.source

    @property
    def page_number(self) -> Optional[int]:
        return self.chunk.page_number

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.chunk.metadata_json or {}


class HybridRetriever:
    """Production hybrid retrieval orchestrator combining semantic dense vectors and lexical search.
    
    Implements Reciprocal Rank Fusion (RRF):
        RRF(d) = sum( 1.0 / (k + rank(d)) ) for rank in [dense_rank, lexical_rank]
    with configurable alpha weighting (lambda blend) and configurable top-k.
    """

    def __init__(
        self,
        db: Session,
        embedder: Optional[LogSemanticEmbeddingService] = None,
        vector_store: Optional[PostgresVectorStore] = None,
        rrf_k: int = 60,
        dense_weight: float = 0.65,
    ) -> None:
        self.db = db
        self.embedder = embedder or LogSemanticEmbeddingService()
        self.vector_store = vector_store or PostgresVectorStore(db)
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        service: Optional[str] = None,
        document_type: Optional[str] = None,
        document_id: Optional[str] = None,
        candidate_multiplier: int = 3,
    ) -> List[RetrievedChunk]:
        """Perform hybrid retrieval on query.
        
        Args:
            query: Natural language query or error log.
            top_k: Number of final chunks to return.
            service: Optional filter by service.
            document_type: Optional filter by document type.
            document_id: Optional filter by specific document.
            candidate_multiplier: Factor to overfetch candidates before fusion (e.g. 3 * top_k).
            
        Returns:
            List of RetrievedChunk objects ordered by descending hybrid fusion score.
        """
        candidate_k = max(top_k * candidate_multiplier, 15)

        # 1. Semantic dense vector retrieval
        query_vec = self.embedder.embed_text(query).tolist()
        dense_results = self.vector_store.semantic_search(
            query_embedding=query_vec,
            top_k=candidate_k,
            service=service,
            document_type=document_type,
            document_id=document_id,
        )

        # 2. Lexical keyword retrieval
        lexical_results = self.vector_store.lexical_search(
            query=query,
            top_k=candidate_k,
            service=service,
            document_type=document_type,
            document_id=document_id,
        )

        # 3. Reciprocal Rank Fusion (RRF) & Score Normalization
        chunk_map: Dict[str, RAGChunk] = {}
        dense_ranks: Dict[str, int] = {}
        dense_scores: Dict[str, float] = {}
        lexical_ranks: Dict[str, int] = {}
        lexical_scores: Dict[str, float] = {}

        for rank, (chunk, score) in enumerate(dense_results, start=1):
            chunk_map[chunk.id] = chunk
            dense_ranks[chunk.id] = rank
            dense_scores[chunk.id] = score

        for rank, (chunk, score) in enumerate(lexical_results, start=1):
            chunk_map[chunk.id] = chunk
            lexical_ranks[chunk.id] = rank
            lexical_scores[chunk.id] = score

        fused_chunks: List[RetrievedChunk] = []

        for cid, chunk in chunk_map.items():
            d_rank = dense_ranks.get(cid)
            l_rank = lexical_ranks.get(cid)
            d_score = dense_scores.get(cid, 0.0)
            l_score = lexical_scores.get(cid, 0.0)

            # Compute RRF score
            rrf = 0.0
            if d_rank is not None:
                rrf += 1.0 / (self.rrf_k + d_rank)
            if l_rank is not None:
                rrf += 1.0 / (self.rrf_k + l_rank)

            # Blended score: alpha * dense + (1 - alpha) * lexical
            blended = (self.dense_weight * d_score) + ((1.0 - self.dense_weight) * l_score)

            # Combined total score (RRF weighted with blended score)
            final_score = (rrf * 100.0 * 0.5) + (blended * 0.5)

            fused_chunks.append(
                RetrievedChunk(
                    chunk=chunk,
                    score=round(final_score, 4),
                    dense_score=round(d_score, 4) if d_rank is not None else None,
                    lexical_score=round(l_score, 4) if l_rank is not None else None,
                    dense_rank=d_rank,
                    lexical_rank=l_rank,
                    rrf_score=round(rrf, 6),
                )
            )

        # Sort descending by fused score
        fused_chunks.sort(key=lambda x: x.score, reverse=True)
        return fused_chunks[:top_k]
