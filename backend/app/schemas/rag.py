"""Pydantic schemas for RAG ingestion, retrieval, query generation, and evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# --- Ingestion Schemas ---

class DocumentIngestRequest(BaseModel):
    """Payload to ingest a raw text document into the RAG knowledge base."""

    title: str = Field(..., description="Human-readable title of the document")
    content: str = Field(..., description="Raw text or markdown content")
    document_type: str = Field(default="runbook", description="Domain category: runbook, architecture, deployment, aws_operational, database_guide, incident_report")
    service: str = Field(default="global", description="Microservice or subsystem identifier")
    source: str = Field(default="api_upload", description="Origin source path or URI")
    file_format: str = Field(default="markdown", description="File format: markdown, txt, pdf")
    document_id: Optional[str] = Field(default=None, description="Optional custom document ID")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary metadata attributes")


class DocumentIngestResponse(BaseModel):
    """Result of document ingestion."""

    document_id: str
    title: str
    document_type: str
    service: str
    file_format: str
    chunks_created: int
    status: str = "success"
    message: str = "Document successfully chunked, embedded, and stored."


# --- Retrieval Schemas ---

class RetrievalRequest(BaseModel):
    """Payload to retrieve relevant knowledge base chunks."""

    query: str = Field(..., min_length=2, description="Natural language query, symptom, or error message")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of chunks to return")
    service: Optional[str] = Field(default=None, description="Filter by service name")
    document_type: Optional[str] = Field(default=None, description="Filter by document type")
    document_id: Optional[str] = Field(default=None, description="Filter by specific document ID")
    use_reranking: bool = Field(default=True, description="Whether to apply contextual reranking")


class RetrievedChunkSchema(BaseModel):
    """Schema representing an individual retrieved chunk."""

    chunk_id: str
    document_id: str
    section: str
    service: str
    document_type: str
    score: float
    content: str
    source: str
    page_number: Optional[int] = None
    dense_score: Optional[float] = None
    lexical_score: Optional[float] = None
    rrf_score: Optional[float] = None


class RetrievalResponse(BaseModel):
    """Result of hybrid chunk retrieval."""

    query: str
    total_retrieved: int
    chunks: List[RetrievedChunkSchema]


# --- Grounded Query & Citations Schemas ---

class RAGQueryRequest(BaseModel):
    """End-to-end question answering query request."""

    query: str = Field(..., min_length=2, description="Operational question, symptom, or error log")
    top_k: int = Field(default=4, ge=1, le=20, description="Number of evidence chunks to retrieve and ground against")
    service: Optional[str] = Field(default=None, description="Optional service scope filter")
    document_type: Optional[str] = Field(default=None, description="Optional document type filter")
    document_id: Optional[str] = Field(default=None, description="Optional document ID filter")
    max_context_tokens: int = Field(default=2500, ge=500, le=8000, description="Token ceiling for retrieved context")


class SourceCitationSchema(BaseModel):
    """Citation identifying evidence used to ground generated answers."""

    source_index: int
    document_id: str
    document_title: str
    section: str
    service: str
    document_type: str
    source: str
    page_number: Optional[int] = None
    relevance_score: float
    snippet: str


class RAGQueryResponse(BaseModel):
    """End-to-end grounded RAG response."""

    query: str
    answer: str
    confidence_score: float
    has_sufficient_evidence: bool
    context_tokens: int
    used_sources_count: int
    citations: List[SourceCitationSchema]


# --- Document Management Schemas ---

class DocumentSummarySchema(BaseModel):
    """Summary of an ingested knowledge base document."""

    id: str
    title: str
    document_type: str
    service: str
    source: str
    file_format: str
    chunk_count: int
    created_at: datetime


class DocumentListResponse(BaseModel):
    """List of ingested documents."""

    total: int
    documents: List[DocumentSummarySchema]


# --- Evaluation Schemas ---

class EvaluationRunRequest(BaseModel):
    """Trigger execution of RAG evaluation benchmark."""

    top_k: int = Field(default=4, ge=1, le=10, description="Top-K retrieval depth for evaluation")


class SampleEvalDetail(BaseModel):
    sample_id: str
    domain: str
    retrieval_relevance: float
    retrieval_recall: float
    answer_faithfulness: float
    answer_relevance: float
    sufficient_evidence: bool


class EvaluationRunResponse(BaseModel):
    """Quantitative evaluation report."""

    total_samples: int
    mean_retrieval_relevance: float
    mean_retrieval_recall: float
    mean_answer_faithfulness: float
    mean_answer_relevance: float
    unanswerable_rejection_accuracy: float
    sample_details: List[SampleEvalDetail]
