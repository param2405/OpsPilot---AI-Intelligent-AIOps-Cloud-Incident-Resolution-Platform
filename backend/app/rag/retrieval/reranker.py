"""Contextual reranker for refining and re-scoring candidate chunks."""

from __future__ import annotations

import logging
import re
from typing import List, Optional
import numpy as np

from app.rag.embeddings.service import LogSemanticEmbeddingService
from app.rag.retrieval.hybrid_search import RetrievedChunk

logger = logging.getLogger(__name__)


class ContextualReranker:
    """Production cross-scoring reranker for retrieved knowledge chunks.
    
    Re-scores candidate chunks through a multi-factor contextual scoring function:
      1. Base Hybrid / RRF Score (weight: 0.35)
      2. Dense semantic similarity between query and full chunk text (weight: 0.35)
      3. Technical entity & error code exact match bonus (weight: 0.15)
      4. Section title intent alignment bonus (weight: 0.15)
    """

    def __init__(self, embedder: Optional[LogSemanticEmbeddingService] = None) -> None:
        self.embedder = embedder or LogSemanticEmbeddingService()

    def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        """Rerank candidate chunks according to multi-factor contextual relevance.
        
        Args:
            query: User question or error log string.
            candidates: Candidate chunks from hybrid retriever.
            top_k: Final number of chunks to return.
            
        Returns:
            Re-ordered and scored list of top_k chunks.
        """
        if not candidates:
            return []

        query_vec = self.embedder.embed_text(query)
        query_terms = set(re.findall(r"\b\w{3,}\b", query.lower()))
        
        # Technical keywords and error patterns
        tech_entities = set(re.findall(r"[A-Z0-9_]{4,}|[a-z0-9_]+-[a-z0-9_]+|[a-z0-9_]+\.[a-z0-9_]+", query))

        # Check intent cues
        is_diagnostic_query = any(k in query.lower() for k in ["diagnos", "detect", "symptom", "metric", "why", "cause"])
        is_remediation_query = any(k in query.lower() for k in ["fix", "remediat", "resolve", "action", "recover", "command", "step"])

        reranked_chunks: List[RetrievedChunk] = []

        # Batch encode candidates for precise semantic similarity
        candidate_texts = [c.content for c in candidates]
        candidate_vecs = self.embedder.embed_batch(candidate_texts)

        for idx, item in enumerate(candidates):
            # Factor 1: Normalized base hybrid score
            base_score = min(1.0, max(0.0, item.score))

            # Factor 2: Dense cosine similarity
            sim = float(np.dot(candidate_vecs[idx], query_vec))
            sim_score = max(0.0, sim)

            # Factor 3: Technical entity overlap
            chunk_text = item.content
            chunk_lower = chunk_text.lower()
            entity_matches = sum(1 for e in tech_entities if e in chunk_text)
            term_matches = sum(1 for t in query_terms if t in chunk_lower)
            lexical_density = 0.0
            if query_terms:
                lexical_density = min(1.0, (term_matches + (entity_matches * 2)) / (len(query_terms) + 1))

            # Factor 4: Section title alignment
            sec_lower = (item.section or "").lower()
            section_boost = 0.0
            if is_diagnostic_query and any(w in sec_lower for w in ["diagnos", "symptom", "root cause", "analysis", "metric"]):
                section_boost = 0.2
            elif is_remediation_query and any(w in sec_lower for w in ["remediat", "action", "step", "recovery", "tuning", "resolution"]):
                section_boost = 0.2

            # Weighted combination
            final_rerank_score = (
                (base_score * 0.30)
                + (sim_score * 0.35)
                + (lexical_density * 0.20)
                + (section_boost * 0.15)
            )

            # Update score
            item.score = round(final_rerank_score, 4)
            reranked_chunks.append(item)

        # Sort descending
        reranked_chunks.sort(key=lambda x: x.score, reverse=True)
        return reranked_chunks[:top_k]
