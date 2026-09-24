"""Context builder assembling retrieved chunks into structured context blocks with citations."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional

from app.rag.retrieval.hybrid_search import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class SourceCitation:
    """Citation metadata corresponding to a numbered source block."""

    source_index: int
    document_id: str
    document_title: str
    section: str
    service: str
    document_type: str
    source: str
    page_number: Optional[int]
    relevance_score: float
    snippet: str


@dataclass
class AssembledContext:
    """Structured context block ready for LLM consumption with citation tracking."""

    formatted_context: str
    citations: List[SourceCitation] = field(default_factory=list)
    total_chunks: int = 0
    total_tokens: int = 0


class ContextBuilder:
    """Assembles retrieved evidence chunks into structured, token-bounded prompt contexts.
    
    Prepends unambiguous source headers:
        [SOURCE X: document_id § section_title (service: service_name)]
    to guarantee the LLM can precisely attribute assertions to specific operational documentation.
    """

    def __init__(self, max_tokens: int = 2500) -> None:
        self.max_tokens = max_tokens

    def build_context(self, chunks: List[RetrievedChunk]) -> AssembledContext:
        """Format retrieved chunks into a prompt context string with numbered citations.
        
        Args:
            chunks: Ranked retrieved chunks.
            
        Returns:
            AssembledContext object with formatted context and citation mappings.
        """
        if not chunks:
            return AssembledContext(
                formatted_context="[NO RELEVANT DOCUMENTATION RETRIEVED]",
                citations=[],
                total_chunks=0,
                total_tokens=0,
            )

        context_blocks: List[str] = []
        citations: List[SourceCitation] = []
        current_tokens = 0

        for idx, chunk in enumerate(chunks, start=1):
            doc_title = chunk.metadata.get("document_title", chunk.document_id)
            source_tag = f"[SOURCE {idx}: {chunk.document_id} § {chunk.section} (service: {chunk.service})]"
            
            chunk_body = chunk.content.strip()
            # If the chunk content already has the inject header "[Title § Section]", clean it for clean reading
            lines = chunk_body.splitlines()
            if lines and lines[0].startswith("[") and lines[0].endswith("]"):
                clean_body = "\n".join(lines[1:]).strip()
            else:
                clean_body = chunk_body

            block = f"{source_tag}\n{clean_body}\n"
            block_tokens = len(block.split())

            if current_tokens + block_tokens > self.max_tokens and context_blocks:
                logger.info("Context length ceiling reached; stopped at %d chunks (%d tokens)", idx - 1, current_tokens)
                break

            context_blocks.append(block)
            current_tokens += block_tokens

            # Create citation entry
            snippet = clean_body[:200] + "..." if len(clean_body) > 200 else clean_body
            citations.append(
                SourceCitation(
                    source_index=idx,
                    document_id=chunk.document_id,
                    document_title=doc_title,
                    section=chunk.section,
                    service=chunk.service,
                    document_type=chunk.document_type,
                    source=chunk.source,
                    page_number=chunk.page_number,
                    relevance_score=chunk.score,
                    snippet=snippet,
                )
            )

        assembled_text = "\n---\n".join(context_blocks)
        return AssembledContext(
            formatted_context=assembled_text,
            citations=citations,
            total_chunks=len(citations),
            total_tokens=current_tokens,
        )
