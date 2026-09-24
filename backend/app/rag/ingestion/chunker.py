"""Section-aware document chunking with contextual header preservation and sliding overlap."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional

from app.rag.ingestion.extractors import ExtractedDocument, ExtractedSection


@dataclass
class ProcessedChunk:
    """Individual chunk produced by SectionAwareChunker ready for vector embedding."""

    id: str
    document_id: str
    chunk_index: int
    content: str
    section: str
    page_number: Optional[int]
    token_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class SectionAwareChunker:
    """Splits structured documents along semantic section boundaries with sliding token overlap.
    
    Contextual Header Injection:
    Prepends '[Document Title § Section Title]' to each chunk. This ensures that when individual
    chunks are embedded into vector space, they carry the macro domain context (e.g. knowing that
    a command belongs to 'PostgreSQL Failover' rather than 'Redis Restart').
    """

    def __init__(
        self,
        chunk_size_words: int = 250,
        overlap_words: int = 40,
        inject_headers: bool = True,
    ) -> None:
        self.chunk_size_words = chunk_size_words
        self.overlap_words = overlap_words
        self.inject_headers = inject_headers

    def chunk_document(
        self,
        doc: ExtractedDocument,
        document_id: str,
        service: str = "global",
        document_type: str = "runbook",
    ) -> List[ProcessedChunk]:
        """Convert an extracted document into structured, enriched chunks."""
        chunks: List[ProcessedChunk] = []
        chunk_counter = 0

        for sec in doc.sections:
            sec_text = sec.content.strip()
            if not sec_text:
                continue

            words = sec_text.split()
            header_prefix = f"[{doc.title} § {sec.title}]\n" if self.inject_headers else ""

            # If section fits within a single chunk
            if len(words) <= self.chunk_size_words:
                content = header_prefix + sec_text
                chunk_id = f"{document_id}_{chunk_counter:03d}"
                chunks.append(
                    ProcessedChunk(
                        id=chunk_id,
                        document_id=document_id,
                        chunk_index=chunk_counter,
                        content=content,
                        section=sec.title,
                        page_number=sec.page_number,
                        token_count=len(content.split()),
                        metadata={
                            "document_title": doc.title,
                            "service": service,
                            "document_type": document_type,
                            "section": sec.title,
                            "page_number": sec.page_number,
                            **doc.metadata,
                        },
                    )
                )
                chunk_counter += 1
                continue

            # Sliding window over long sections
            step = max(1, self.chunk_size_words - self.overlap_words)
            for start_idx in range(0, len(words), step):
                window_words = words[start_idx : start_idx + self.chunk_size_words]
                if not window_words:
                    break

                chunk_body = " ".join(window_words)
                content = header_prefix + chunk_body
                chunk_id = f"{document_id}_{chunk_counter:03d}"

                chunks.append(
                    ProcessedChunk(
                        id=chunk_id,
                        document_id=document_id,
                        chunk_index=chunk_counter,
                        content=content,
                        section=sec.title,
                        page_number=sec.page_number,
                        token_count=len(content.split()),
                        metadata={
                            "document_title": doc.title,
                            "service": service,
                            "document_type": document_type,
                            "section": sec.title,
                            "page_number": sec.page_number,
                            "start_word": start_idx,
                            **doc.metadata,
                        },
                    )
                )
                chunk_counter += 1

                if start_idx + self.chunk_size_words >= len(words):
                    break

        return chunks
