"""Integration tests for PostgresVectorStore, HybridRetriever, and ContextualReranker."""

from __future__ import annotations

import pytest
from app.db.session import SessionLocal
from app.rag.embeddings.service import LogSemanticEmbeddingService
from app.rag.retrieval.hybrid_search import HybridRetriever
from app.rag.retrieval.reranker import ContextualReranker
from app.rag.retrieval.vector_store import PostgresVectorStore


@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    yield session
    session.close()


def test_vector_store_listing(db_session):
    store = PostgresVectorStore(db_session)
    docs = store.list_documents(limit=10)
    assert len(docs) > 0
    first_doc = docs[0]
    chunks = store.list_chunks_for_document(first_doc.id)
    assert len(chunks) > 0


def test_semantic_search(db_session):
    store = PostgresVectorStore(db_session)
    embedder = LogSemanticEmbeddingService()
    query_vec = embedder.embed_text("PostgreSQL connection pool HikariCP exhausted").tolist()

    results = store.semantic_search(query_vec, top_k=3)
    assert len(results) > 0
    top_chunk, score = results[0]
    assert score > 0.0
    assert top_chunk.id is not None


def test_lexical_search(db_session):
    store = PostgresVectorStore(db_session)
    results = store.lexical_search("Aurora failover replica lag", top_k=3)
    assert len(results) > 0
    top_chunk, score = results[0]
    assert "aurora" in top_chunk.content.lower() or "failover" in top_chunk.content.lower()


def test_hybrid_retriever_rrf(db_session):
    retriever = HybridRetriever(db_session)
    chunks = retriever.retrieve("JVM OutOfMemoryError heap dump", top_k=4)
    assert len(chunks) > 0
    top = chunks[0]
    assert top.score > 0.0
    assert top.rrf_score > 0.0
    assert "jvm" in top.content.lower() or "oom" in top.content.lower() or "memory" in top.content.lower()


def test_contextual_reranker(db_session):
    retriever = HybridRetriever(db_session)
    reranker = ContextualReranker()
    cands = retriever.retrieve("pg_terminate_backend idle in transaction", top_k=6)
    reranked = reranker.rerank("pg_terminate_backend idle in transaction", cands, top_k=3)
    assert len(reranked) <= 3
    assert len(reranked) > 0
    # Top reranked chunk should contain diagnostic or remediation terms
    assert any("idle in transaction" in c.content.lower() for c in reranked)
