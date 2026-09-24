"""Unit tests for ContextBuilder and GroundedGenerator."""

from __future__ import annotations

import pytest
from app.db.session import SessionLocal
from app.rag.generation.context_builder import ContextBuilder
from app.rag.generation.grounded_generator import GroundedGenerator
from app.rag.retrieval.hybrid_search import HybridRetriever


@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    yield session
    session.close()


def test_context_builder(db_session):
    retriever = HybridRetriever(db_session)
    builder = ContextBuilder(max_tokens=1500)
    chunks = retriever.retrieve("PostgreSQL pool", top_k=3)
    
    context = builder.build_context(chunks)
    assert context.total_chunks > 0
    assert "[SOURCE 1:" in context.formatted_context
    assert len(context.citations) == context.total_chunks
    assert context.citations[0].source_index == 1
    assert context.citations[0].relevance_score > 0.0


def test_grounded_generator_sufficient_evidence(db_session):
    retriever = HybridRetriever(db_session)
    builder = ContextBuilder()
    generator = GroundedGenerator()

    query = "How do you identify idle in transaction sessions in PostgreSQL?"
    chunks = retriever.retrieve(query, top_k=3)
    context = builder.build_context(chunks)

    response = generator.generate(query, context)
    assert response.has_sufficient_evidence is True
    assert response.confidence_score > 0.2
    assert "[SOURCE" in response.answer
    assert len(response.citations) > 0


def test_grounded_generator_insufficient_evidence(db_session):
    builder = ContextBuilder()
    generator = GroundedGenerator()

    # Empty context
    empty_context = builder.build_context([])
    res_empty = generator.generate("How to configure quantum teleportation?", empty_context)
    assert res_empty.has_sufficient_evidence is False
    assert "insufficient evidence" in res_empty.answer.lower()

    # Out-of-domain query with irrelevant context
    retriever = HybridRetriever(db_session)
    irrelevant_chunks = retriever.retrieve("quantum teleportation Azure", top_k=3)
    irrelevant_context = builder.build_context(irrelevant_chunks)
    res_unrelated = generator.generate("How do you configure quantum teleportation on Azure?", irrelevant_context)
    assert res_unrelated.has_sufficient_evidence is False
    assert "insufficient evidence" in res_unrelated.answer.lower()
