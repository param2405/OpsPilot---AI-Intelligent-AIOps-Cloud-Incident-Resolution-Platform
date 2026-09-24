"""FastAPI endpoints for Production RAG System: Ingestion, Retrieval, Grounded QA, and Evaluation."""

from __future__ import annotations

import logging
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.rag import RAGChunk, RAGDocument
from app.rag.embeddings.service import LogSemanticEmbeddingService
from app.rag.evaluation.dataset import EVALUATION_DATASET
from app.rag.evaluation.evaluator import RAGEvaluator
from app.rag.generation.context_builder import ContextBuilder
from app.rag.generation.grounded_generator import GroundedGenerator
from app.rag.ingestion.pipeline import RAGIngestionPipeline
from app.rag.retrieval.hybrid_search import HybridRetriever
from app.rag.retrieval.reranker import ContextualReranker
from app.rag.retrieval.vector_store import PostgresVectorStore
from app.schemas.rag import (
    DocumentIngestRequest,
    DocumentIngestResponse,
    DocumentListResponse,
    DocumentSummarySchema,
    EvaluationRunRequest,
    EvaluationRunResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedChunkSchema,
    SampleEvalDetail,
    SourceCitationSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG Knowledge System"])

# Shared singleton embedder to avoid re-initializing weights on every request
_embedder_instance: Optional[LogSemanticEmbeddingService] = None


def get_embedder() -> LogSemanticEmbeddingService:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = LogSemanticEmbeddingService()
    return _embedder_instance


@router.post("/ingest", response_model=DocumentIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_document(
    payload: DocumentIngestRequest,
    db: Session = Depends(get_db),
    embedder: LogSemanticEmbeddingService = Depends(get_embedder),
) -> DocumentIngestResponse:
    """Ingest a raw text or markdown document into the knowledge base."""
    pipeline = RAGIngestionPipeline(db=db, embedder=embedder)
    try:
        doc = pipeline.ingest_text(
            raw_text=payload.content,
            document_id=payload.document_id,
            title=payload.title,
            document_type=payload.document_type,
            service=payload.service,
            source=payload.source,
            file_format=payload.file_format,
            metadata=payload.metadata,
        )
        chunk_count = len(doc.chunks)
        return DocumentIngestResponse(
            document_id=doc.id,
            title=doc.title,
            document_type=doc.document_type,
            service=doc.service,
            file_format=doc.file_format,
            chunks_created=chunk_count,
            status="success",
            message=f"Document '{doc.title}' ingested successfully with {chunk_count} chunks.",
        )
    except Exception as exc:
        logger.error("Document ingestion error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest document: {str(exc)}",
        )


@router.post("/retrieve", response_model=RetrievalResponse)
def retrieve_chunks(
    payload: RetrievalRequest,
    db: Session = Depends(get_db),
    embedder: LogSemanticEmbeddingService = Depends(get_embedder),
) -> RetrievalResponse:
    """Perform hybrid retrieval (dense semantic + lexical keyword search + reranking) on chunks."""
    retriever = HybridRetriever(db=db, embedder=embedder)
    reranker = ContextualReranker(embedder=embedder)

    # 1. Retrieve candidates
    candidates = retriever.retrieve(
        query=payload.query,
        top_k=payload.top_k if not payload.use_reranking else payload.top_k * 2,
        service=payload.service,
        document_type=payload.document_type,
        document_id=payload.document_id,
    )

    # 2. Rerank if enabled
    if payload.use_reranking and candidates:
        final_chunks = reranker.rerank(query=payload.query, candidates=candidates, top_k=payload.top_k)
    else:
        final_chunks = candidates[:payload.top_k]

    chunk_schemas = [
        RetrievedChunkSchema(
            chunk_id=c.id,
            document_id=c.document_id,
            section=c.section,
            service=c.service,
            document_type=c.document_type,
            score=c.score,
            content=c.content,
            source=c.source,
            page_number=c.page_number,
            dense_score=c.dense_score,
            lexical_score=c.lexical_score,
            rrf_score=c.rrf_score,
        )
        for c in final_chunks
    ]

    return RetrievalResponse(
        query=payload.query,
        total_retrieved=len(chunk_schemas),
        chunks=chunk_schemas,
    )


@router.post("/query", response_model=RAGQueryResponse)
def query_rag(
    payload: RAGQueryRequest,
    db: Session = Depends(get_db),
    embedder: LogSemanticEmbeddingService = Depends(get_embedder),
) -> RAGQueryResponse:
    """Execute end-to-end grounded question answering with source citations."""
    retriever = HybridRetriever(db=db, embedder=embedder)
    reranker = ContextualReranker(embedder=embedder)
    context_builder = ContextBuilder(max_tokens=payload.max_context_tokens)
    generator = GroundedGenerator()

    # 1. Hybrid retrieval & rerank
    candidates = retriever.retrieve(
        query=payload.query,
        top_k=payload.top_k * 2,
        service=payload.service,
        document_type=payload.document_type,
        document_id=payload.document_id,
    )
    ranked_chunks = reranker.rerank(query=payload.query, candidates=candidates, top_k=payload.top_k)

    # 2. Context construction
    context = context_builder.build_context(ranked_chunks)

    # 3. Grounded generation
    response = generator.generate(query=payload.query, context=context)

    citation_schemas = [
        SourceCitationSchema(
            source_index=c.source_index,
            document_id=c.document_id,
            document_title=c.document_title,
            section=c.section,
            service=c.service,
            document_type=c.document_type,
            source=c.source,
            page_number=c.page_number,
            relevance_score=c.relevance_score,
            snippet=c.snippet,
        )
        for c in response.citations
    ]

    return RAGQueryResponse(
        query=payload.query,
        answer=response.answer,
        confidence_score=response.confidence_score,
        has_sufficient_evidence=response.has_sufficient_evidence,
        context_tokens=response.context_tokens,
        used_sources_count=response.used_sources_count,
        citations=citation_schemas,
    )


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    service: Optional[str] = Query(None, description="Filter by service"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """List ingested knowledge base documents."""
    vector_store = PostgresVectorStore(db)
    docs = vector_store.list_documents(service=service, document_type=document_type, limit=limit)

    summaries = [
        DocumentSummarySchema(
            id=d.id,
            title=d.title,
            document_type=d.document_type,
            service=d.service,
            source=d.source,
            file_format=d.file_format,
            chunk_count=len(d.chunks),
            created_at=d.created_at,
        )
        for d in docs
    ]

    return DocumentListResponse(total=len(summaries), documents=summaries)


@router.get("/documents/{document_id}")
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve full raw document and all associated chunks."""
    vector_store = PostgresVectorStore(db)
    doc = vector_store.get_document_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )

    chunks = vector_store.list_chunks_for_document(document_id)
    return {
        "id": doc.id,
        "title": doc.title,
        "document_type": doc.document_type,
        "service": doc.service,
        "source": doc.source,
        "file_format": doc.file_format,
        "raw_content": doc.raw_content,
        "created_at": doc.created_at,
        "total_chunks": len(chunks),
        "chunks": [
            {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "section": c.section,
                "token_count": c.token_count,
                "content": c.content,
            }
            for c in chunks
        ],
    }


@router.post("/evaluate", response_model=EvaluationRunResponse)
def evaluate_rag(
    payload: EvaluationRunRequest = EvaluationRunRequest(),
    db: Session = Depends(get_db),
    embedder: LogSemanticEmbeddingService = Depends(get_embedder),
) -> EvaluationRunResponse:
    """Run the quantitative evaluation benchmark and return precision, recall, faithfulness, and relevance metrics."""
    evaluator = RAGEvaluator(db=db, embedder=embedder)
    summary = evaluator.evaluate_benchmark(top_k=payload.top_k)

    sample_details = [
        SampleEvalDetail(
            sample_id=s.sample_id,
            domain=s.domain,
            retrieval_relevance=s.retrieval_relevance,
            retrieval_recall=s.retrieval_recall,
            answer_faithfulness=s.answer_faithfulness,
            answer_relevance=s.answer_relevance,
            sufficient_evidence=s.has_sufficient_evidence,
        )
        for s in summary.samples
    ]

    return EvaluationRunResponse(
        total_samples=summary.total_samples,
        mean_retrieval_relevance=summary.mean_retrieval_relevance,
        mean_retrieval_recall=summary.mean_retrieval_recall,
        mean_answer_faithfulness=summary.mean_answer_faithfulness,
        mean_answer_relevance=summary.mean_answer_relevance,
        unanswerable_rejection_accuracy=summary.unanswerable_rejection_accuracy,
        sample_details=sample_details,
    )


@router.post("/seed")
def seed_knowledge_base(
    db: Session = Depends(get_db),
    embedder: LogSemanticEmbeddingService = Depends(get_embedder),
):
    """Seed the database with all built-in knowledge base operational documentation."""
    pipeline = RAGIngestionPipeline(db=db, embedder=embedder)
    kb_dir = os.path.join(os.path.dirname(__file__), "..", "..", "rag", "knowledge_base")
    kb_dir = os.path.abspath(kb_dir)

    if not os.path.exists(kb_dir):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge base directory not found at {kb_dir}",
        )

    ingested = pipeline.ingest_directory(kb_dir)
    return {
        "status": "success",
        "message": f"Successfully ingested {len(ingested)} knowledge base documents.",
        "documents": [{"id": d.id, "title": d.title, "type": d.document_type, "chunks": len(d.chunks)} for d in ingested],
    }
