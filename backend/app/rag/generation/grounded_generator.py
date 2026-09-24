"""Grounded LLM generator with strict evidence synthesis, citations, and insufficient evidence fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional

from app.rag.generation.context_builder import AssembledContext, SourceCitation

logger = logging.getLogger(__name__)


SYSTEM_GROUNDING_PROMPT = """You are OpsPilot AI, an expert autonomous Site Reliability Engineering (SRE) copilot.
Your job is to provide accurate, actionable operational answers grounded STRICTLY in the provided context.

RULES:
1. Grounding: Answer ONLY using the facts, procedures, metrics, and configurations present in the provided context.
2. Citations: Cite your sources inline using bracketed notation like [SOURCE 1] or [SOURCE 2] immediately after each fact or recommendation.
3. Unsupported Claims: Do NOT extrapolate, speculate, or introduce external knowledge not grounded in the context.
4. Insufficient Evidence: If the provided context does not contain enough information to answer the question with certainty, you MUST explicitly state: "Based on the retrieved documentation, there is insufficient evidence to answer this question." Do not attempt to guess.
5. Actionability: When explaining remediation, provide exact commands and config parameters as specified in the evidence.
"""


@dataclass
class GroundedResponse:
    """End-to-end response produced by the GroundedGenerator."""

    answer: str
    citations: List[SourceCitation]
    confidence_score: float
    has_sufficient_evidence: bool
    context_tokens: int
    used_sources_count: int


class GroundedGenerator:
    """Executes grounded question answering with strict hallucination controls and source citations.
    
    Supports:
      1. Pluggable external LLM completion callback (OpenAI, Anthropic, Gemini, Ollama, vLLM).
      2. Deterministic, high-fidelity local synthesis engine when running in offline/air-gapped environments.
    """

    def __init__(
        self,
        llm_client: Optional[Callable[[str, str], str]] = None,
        min_relevance_threshold: float = 0.20,
    ) -> None:
        self.llm_client = llm_client
        self.min_relevance_threshold = min_relevance_threshold

    def generate(
        self,
        query: str,
        context: AssembledContext,
    ) -> GroundedResponse:
        """Generate a grounded answer for the user query using the assembled context.
        
        Args:
            query: User question or incident log.
            context: AssembledContext from ContextBuilder.
            
        Returns:
            GroundedResponse with cited answer and evidence metadata.
        """
        # Step 1: Check for insufficient evidence
        if not context.citations or context.total_chunks == 0:
            return GroundedResponse(
                answer="Based on the retrieved documentation, there is insufficient evidence to answer this question. No matching runbooks, architecture documents, or incident postmortems were found in the knowledge base.",
                citations=[],
                confidence_score=0.0,
                has_sufficient_evidence=False,
                context_tokens=0,
                used_sources_count=0,
            )

        # Evaluate subject term coverage across retrieved context
        stop_words = {
            "what", "when", "where", "which", "who", "whom", "this", "that", "these", "those",
            "have", "been", "were", "with", "from", "your", "does", "doing", "done", "about",
            "into", "through", "after", "before", "during", "show", "tell", "explain", "describe",
            "configure", "cause", "causes", "causing", "difference", "between", "when", "upon",
            "identify", "detect", "check", "find", "resolve", "remediate", "handle", "mitigate",
            "diagnose", "perform", "execute", "should", "would", "could", "using", "works",
            "service", "services", "system", "systems", "application", "applications",
            "workload", "workloads", "instance", "instances",
        }
        raw_words = re.findall(r"\b[a-zA-Z0-9_\-\.]{4,}\b", query.lower())
        subject_terms = [w for w in raw_words if w not in stop_words]

        context_corpus = context.formatted_context.lower()
        
        term_matches = sum(1 for t in subject_terms if t in context_corpus) if subject_terms else 0
        term_coverage = (term_matches / len(subject_terms)) if subject_terms else 1.0

        max_chunk_score = max(c.relevance_score for c in context.citations)
        
        # If both score and subject term coverage indicate weak relevance
        if max_chunk_score < self.min_relevance_threshold or (subject_terms and term_coverage < 0.35):
            return GroundedResponse(
                answer=(
                    f"Based on the retrieved documentation, there is insufficient evidence to answer '{query}'. "
                    f"The available knowledge base (runbooks, architecture, deployment, AWS, database, and incident reports) "
                    f"does not cover this topic (subject coverage: {term_coverage * 100:.1f}%)."
                ),
                citations=context.citations,
                confidence_score=round(max_chunk_score * term_coverage, 4),
                has_sufficient_evidence=False,
                context_tokens=context.total_tokens,
                used_sources_count=0,
            )

        # Step 2: If external LLM callback is provided, invoke it
        if self.llm_client is not None:
            try:
                user_prompt = f"Operational Documentation Context:\n{context.formatted_context}\n\nQuestion / Incident:\n{query}"
                raw_answer = self.llm_client(SYSTEM_GROUNDING_PROMPT, user_prompt)
                
                # Check if LLM flagged insufficient evidence
                insufficient = "insufficient evidence" in raw_answer.lower()
                used_sources = len(set(re.findall(r"\[SOURCE\s*(\d+)\]", raw_answer)))

                return GroundedResponse(
                    answer=raw_answer.strip(),
                    citations=context.citations,
                    confidence_score=round(min(1.0, max_chunk_score * 1.1), 4),
                    has_sufficient_evidence=not insufficient,
                    context_tokens=context.total_tokens,
                    used_sources_count=used_sources,
                )
            except Exception as exc:
                logger.warning("External LLM invocation failed (%s); falling back to local grounded synthesis", exc)

        # Step 3: High-fidelity local deterministic synthesis engine
        return self._synthesize_local_grounded_answer(query, context, max_chunk_score)

    def _synthesize_local_grounded_answer(
        self,
        query: str,
        context: AssembledContext,
        max_score: float,
    ) -> GroundedResponse:
        """Deterministic, grounded evidence synthesizer when no external LLM API is connected."""
        query_words = set(re.findall(r"\b\w{3,}\b", query.lower()))
        
        # Analyze which sources address the query
        relevant_citations: List[SourceCitation] = []
        synthesized_paragraphs: List[str] = []

        for cit in context.citations:
            # Check if this citation is sufficiently relevant
            if cit.relevance_score < self.min_relevance_threshold:
                continue

            relevant_citations.append(cit)

        if not relevant_citations:
            return GroundedResponse(
                answer="Based on the retrieved documentation, there is insufficient evidence to address the query.",
                citations=[],
                confidence_score=0.0,
                has_sufficient_evidence=False,
                context_tokens=context.total_tokens,
                used_sources_count=0,
            )

        # Structure grounded synthesis
        top_cit = relevant_citations[0]
        intro = f"According to the operational documentation for **{top_cit.document_title}** [SOURCE {top_cit.source_index}]:"
        synthesized_paragraphs.append(intro)

        # Extract salient points from the top citations
        for cit in relevant_citations[:3]:
            sec_heading = f"### {cit.section} ([SOURCE {cit.source_index}])"
            lines = [line.strip() for line in cit.snippet.splitlines() if line.strip() and not line.strip().startswith("[SOURCE")]
            
            # Format snippet points
            body_points = []
            for line in lines[:4]:
                if line.startswith("-") or line.startswith("*") or line.startswith("1.") or line.startswith("```"):
                    body_points.append(f"{line} [SOURCE {cit.source_index}]")
                elif len(line) > 20:
                    body_points.append(f"- {line} [SOURCE {cit.source_index}]")

            if body_points:
                synthesized_paragraphs.append(sec_heading + "\n" + "\n".join(body_points))

        full_answer = "\n\n".join(synthesized_paragraphs)
        used_sources = len(relevant_citations[:3])

        return GroundedResponse(
            answer=full_answer,
            citations=context.citations,
            confidence_score=round(min(1.0, max_score), 4),
            has_sufficient_evidence=True,
            context_tokens=context.total_tokens,
            used_sources_count=used_sources,
        )
