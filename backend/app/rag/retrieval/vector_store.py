"""PostgreSQL vector store using pgvector with hybrid semantic and lexical capabilities."""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.models.rag import RAGChunk, RAGDocument

logger = logging.getLogger(__name__)


class PostgresVectorStore:
    """Production vector storage and search engine utilizing PostgreSQL pgvector.
    
    Supports:
      1. Dense vector similarity search using L2-normalized cosine distance (<=> operator).
      2. Lexical keyword search using PostgreSQL full-text search (tsvector/plainto_tsquery)
         with graceful SQLite/fallback BM25-style ranking.
      3. Granular metadata filtering by service, document_type, and document_id.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._is_postgres = self._check_postgres()

    def _check_postgres(self) -> bool:
        """Determine whether the underlying database dialect is PostgreSQL."""
        try:
            bind = self.db.get_bind()
            return bind.dialect.name == "postgresql"
        except Exception:
            return False

    def semantic_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        service: Optional[str] = None,
        document_type: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> List[Tuple[RAGChunk, float]]:
        """Perform dense semantic similarity search against chunk vector embeddings.
        
        Returns:
            List of (RAGChunk, similarity_score) tuples where similarity_score is in [0.0, 1.0].
        """
        if self._is_postgres:
            try:
                # PostgreSQL native pgvector cosine distance
                dist_expr = RAGChunk.embedding.cosine_distance(query_embedding).label("distance")
                stmt = select(RAGChunk, dist_expr)

                if service:
                    stmt = stmt.where(RAGChunk.service == service)
                if document_type:
                    stmt = stmt.where(RAGChunk.document_type == document_type)
                if document_id:
                    stmt = stmt.where(RAGChunk.document_id == document_id)

                stmt = stmt.order_by(dist_expr.asc()).limit(top_k)
                results = self.db.execute(stmt).all()

                return [(row[0], float(max(0.0, 1.0 - (row[1] or 0.0)))) for row in results]
            except Exception as exc:
                logger.warning("Postgres pgvector query failed (%s); falling back to in-memory search", exc)

        # Fallback for SQLite or local testing
        return self._fallback_semantic_search(
            query_embedding=query_embedding,
            top_k=top_k,
            service=service,
            document_type=document_type,
            document_id=document_id,
        )

    def _fallback_semantic_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        service: Optional[str] = None,
        document_type: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> List[Tuple[RAGChunk, float]]:
        """In-memory cosine similarity fallback."""
        stmt = select(RAGChunk)
        if service:
            stmt = stmt.where(RAGChunk.service == service)
        if document_type:
            stmt = stmt.where(RAGChunk.document_type == document_type)
        if document_id:
            stmt = stmt.where(RAGChunk.document_id == document_id)

        chunks = self.db.execute(stmt).scalars().all()
        if not chunks:
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)
        if q_norm == 0:
            return [(c, 0.0) for c in chunks[:top_k]]

        scored: List[Tuple[RAGChunk, float]] = []
        for c in chunks:
            if not c.embedding:
                continue
            c_vec = np.array(c.embedding, dtype=np.float32)
            c_norm = np.linalg.norm(c_vec)
            if c_norm == 0:
                score = 0.0
            else:
                score = float(np.dot(query_vec, c_vec) / (q_norm * c_norm))
            scored.append((c, max(0.0, score)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def lexical_search(
        self,
        query: str,
        top_k: int = 5,
        service: Optional[str] = None,
        document_type: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> List[Tuple[RAGChunk, float]]:
        """Perform lexical keyword search using PostgreSQL full-text search or BM25-style token overlap.
        
        Returns:
            List of (RAGChunk, lexical_score) tuples where lexical_score is normalized in [0.0, 1.0].
        """
        terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) >= 2]
        if not terms:
            return []

        if self._is_postgres:
            try:
                # PostgreSQL full text search with ts_rank
                clean_query = " | ".join(terms)
                ts_query = func.plainto_tsquery("english", query)
                ts_vector = func.to_tsvector("english", RAGChunk.content)
                rank_expr = func.ts_rank(ts_vector, ts_query).label("rank")

                stmt = (
                    select(RAGChunk, rank_expr)
                    .where(ts_vector.op("@@")(ts_query))
                )
                if service:
                    stmt = stmt.where(RAGChunk.service == service)
                if document_type:
                    stmt = stmt.where(RAGChunk.document_type == document_type)
                if document_id:
                    stmt = stmt.where(RAGChunk.document_id == document_id)

                stmt = stmt.order_by(rank_expr.desc()).limit(top_k)
                results = self.db.execute(stmt).all()

                if results:
                    max_rank = max(float(r[1] or 1.0) for r in results) or 1.0
                    return [(row[0], float((row[1] or 0.0) / max_rank)) for row in results]
            except Exception as exc:
                logger.warning("Postgres tsvector search failed (%s); falling back to lexical overlap", exc)

        # Fallback lexical scoring (token overlap + section matching)
        return self._fallback_lexical_search(
            terms=terms,
            top_k=top_k,
            service=service,
            document_type=document_type,
            document_id=document_id,
        )

    def _fallback_lexical_search(
        self,
        terms: List[str],
        top_k: int = 5,
        service: Optional[str] = None,
        document_type: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> List[Tuple[RAGChunk, float]]:
        """Fallback lexical scorer computing term presence and weighted frequencies."""
        stmt = select(RAGChunk)
        if service:
            stmt = stmt.where(RAGChunk.service == service)
        if document_type:
            stmt = stmt.where(RAGChunk.document_type == document_type)
        if document_id:
            stmt = stmt.where(RAGChunk.document_id == document_id)

        chunks = self.db.execute(stmt).scalars().all()
        if not chunks:
            return []

        scored: List[Tuple[RAGChunk, float]] = []
        for c in chunks:
            content_lower = c.content.lower()
            section_lower = (c.section or "").lower()
            
            # Count term matches
            matches = 0
            for term in terms:
                if term in content_lower:
                    matches += 1
                if term in section_lower:
                    matches += 2  # Section match weight boost

            if matches > 0:
                # Normalize by total terms
                score = min(1.0, float(matches) / float(len(terms) * 2))
                scored.append((c, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def get_chunk_by_id(self, chunk_id: str) -> Optional[RAGChunk]:
        """Fetch a specific chunk by its primary key ID."""
        return self.db.get(RAGChunk, chunk_id)

    def get_document_by_id(self, document_id: str) -> Optional[RAGDocument]:
        """Fetch an ingested document including its raw content."""
        return self.db.get(RAGDocument, document_id)

    def list_documents(
        self,
        service: Optional[str] = None,
        document_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[RAGDocument]:
        """List ingested knowledge base documents."""
        stmt = select(RAGDocument)
        if service:
            stmt = stmt.where(RAGDocument.service == service)
        if document_type:
            stmt = stmt.where(RAGDocument.document_type == document_type)
        stmt = stmt.order_by(RAGDocument.created_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def list_chunks_for_document(self, document_id: str) -> List[RAGChunk]:
        """List all chunks belonging to a document ordered by chunk_index."""
        stmt = select(RAGChunk).where(RAGChunk.document_id == document_id).order_by(RAGChunk.chunk_index.asc())
        return list(self.db.execute(stmt).scalars().all())
