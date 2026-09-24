"""Production RAG ingestion pipeline orchestrating extraction, chunking, embedding, and storage."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Union
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.rag import RAGChunk, RAGDocument
from app.rag.embeddings.service import LogSemanticEmbeddingService
from app.rag.ingestion.chunker import SectionAwareChunker
from app.rag.ingestion.extractors import (
    ExtractedDocument,
    ExtractedSection,
    MarkdownExtractor,
    get_extractor_for_file,
)

logger = logging.getLogger(__name__)


class RAGIngestionPipeline:
    """End-to-end document ingestion pipeline for the OpsPilot AI Knowledge Base."""

    def __init__(
        self,
        db: Session,
        embedder: Optional[LogSemanticEmbeddingService] = None,
        chunker: Optional[SectionAwareChunker] = None,
    ) -> None:
        self.db = db
        self.embedder = embedder or LogSemanticEmbeddingService()
        self.chunker = chunker or SectionAwareChunker()

    def ingest_text(
        self,
        raw_text: str,
        document_id: Optional[str] = None,
        title: Optional[str] = None,
        document_type: str = "runbook",
        service: str = "global",
        source: str = "manual_upload",
        file_format: str = "markdown",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RAGDocument:
        """Ingest raw text string (e.g. from API upload or synthetic generation)."""
        extractor = MarkdownExtractor() if file_format == "markdown" else get_extractor_for_file(f"doc.{file_format}")
        extracted = extractor.extract(
            content_or_path=raw_text,
            filename=f"{document_id}.{file_format}" if document_id else "document",
            metadata={"title": title, **(metadata or {})},
        )
        return self._process_and_store(
            extracted=extracted,
            document_id=document_id or f"doc_{uuid.uuid4().hex[:12]}",
            document_type=document_type,
            service=service,
            source=source,
            file_format=file_format,
            metadata=metadata or {},
        )

    def ingest_file(
        self,
        filepath: str,
        document_id: Optional[str] = None,
        title: Optional[str] = None,
        document_type: str = "runbook",
        service: str = "global",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RAGDocument:
        """Ingest a physical file on disk (Markdown, TXT, or PDF)."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Document file not found: {filepath}")

        extractor = get_extractor_for_file(filepath)
        extracted = extractor.extract(
            content_or_path=filepath,
            filename=os.path.basename(filepath),
            metadata={"title": title, **(metadata or {})},
        )

        doc_id = document_id or f"doc_{os.path.splitext(os.path.basename(filepath))[0]}"
        return self._process_and_store(
            extracted=extracted,
            document_id=doc_id,
            document_type=document_type,
            service=service,
            source=filepath,
            file_format=extracted.file_format,
            metadata=metadata or {},
        )

    def ingest_directory(
        self,
        dirpath: str,
        default_service: str = "global",
        default_document_type: str = "runbook",
    ) -> List[RAGDocument]:
        """Recursively scan and ingest all supported document files (.md, .txt, .pdf) in a folder."""
        ingested: List[RAGDocument] = []
        supported_exts = {".md", ".markdown", ".txt", ".pdf"}

        for root, _, files in os.walk(dirpath):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in supported_exts:
                    fpath = os.path.join(root, file)
                    # Infer document type and service from path if possible
                    rel_path = os.path.relpath(fpath, dirpath).lower()
                    doc_type = default_document_type
                    if "runbook" in rel_path:
                        doc_type = "runbook"
                    elif "architecture" in rel_path:
                        doc_type = "architecture"
                    elif "deployment" in rel_path:
                        doc_type = "deployment"
                    elif "aws" in rel_path:
                        doc_type = "aws_operational"
                    elif "database" in rel_path or "db" in rel_path:
                        doc_type = "database_guide"
                    elif "incident" in rel_path or "postmortem" in rel_path:
                        doc_type = "incident_report"

                    doc = self.ingest_file(
                        filepath=fpath,
                        document_type=doc_type,
                        service=default_service,
                    )
                    ingested.append(doc)

        logger.info("Ingested %d documents from directory %s", len(ingested), dirpath)
        return ingested

    def _process_and_store(
        self,
        extracted: ExtractedDocument,
        document_id: str,
        document_type: str,
        service: str,
        source: str,
        file_format: str,
        metadata: Dict[str, Any],
    ) -> RAGDocument:
        """Internal worker executing chunking, embedding, and idempotent database writing."""
        # 1. Chunk document
        chunks = self.chunker.chunk_document(
            doc=extracted,
            document_id=document_id,
            service=service,
            document_type=document_type,
        )

        if not chunks:
            # Fallback for empty document
            chunks = self.chunker.chunk_document(
                doc=ExtractedDocument(
                    title=extracted.title,
                    raw_content=extracted.raw_content,
                    file_format=file_format,
                    sections=[ExtractedSection(title="Body", content=extracted.raw_content)],
                ),
                document_id=document_id,
                service=service,
                document_type=document_type,
            )

        # 2. Compute batch vector embeddings
        chunk_texts = [c.content for c in chunks]
        embeddings_matrix = self.embedder.embed_batch(chunk_texts)  # [NumChunks, 128]

        # 3. Idempotently remove prior document if updating
        existing_doc = self.db.get(RAGDocument, document_id)
        if existing_doc:
            self.db.delete(existing_doc)
            self.db.flush()

        # 4. Create RAGDocument model (stores original raw content)
        doc_model = RAGDocument(
            id=document_id,
            title=extracted.title,
            document_type=document_type,
            source=source,
            service=service,
            raw_content=extracted.raw_content,
            file_format=file_format,
            metadata_json=metadata,
        )
        self.db.add(doc_model)

        # 5. Create RAGChunk models with embeddings
        for idx, chunk in enumerate(chunks):
            embed_vec = embeddings_matrix[idx].tolist()
            chunk_model = RAGChunk(
                id=chunk.id,
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                section=chunk.section,
                page_number=chunk.page_number,
                service=service,
                document_type=document_type,
                source=source,
                token_count=chunk.token_count,
                embedding=embed_vec,
                metadata_json=chunk.metadata,
            )
            self.db.add(chunk_model)

        self.db.commit()
        self.db.refresh(doc_model)
        logger.info(
            "Successfully ingested document '%s' (%s) with %d chunks into database.",
            doc_model.title,
            doc_model.id,
            len(chunks),
        )
        return doc_model
