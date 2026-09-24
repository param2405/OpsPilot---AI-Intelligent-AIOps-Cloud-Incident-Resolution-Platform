"""Unit tests for SectionAwareChunker."""

from __future__ import annotations

import pytest
from app.rag.ingestion.chunker import SectionAwareChunker
from app.rag.ingestion.extractors import ExtractedDocument, ExtractedSection


def test_chunker_small_section():
    chunker = SectionAwareChunker(chunk_size_words=100, overlap_words=20)
    doc = ExtractedDocument(
        title="Sample Runbook",
        raw_content="Small content",
        file_format="markdown",
        sections=[
            ExtractedSection(title="Overview", content="This is a quick summary of the service."),
            ExtractedSection(title="Remediation", content="Execute rollout restart."),
        ],
    )
    chunks = chunker.chunk_document(doc, document_id="doc_test")
    assert len(chunks) == 2
    assert chunks[0].id == "doc_test_000"
    assert chunks[1].id == "doc_test_001"
    assert "[Sample Runbook § Overview]" in chunks[0].content
    assert "[Sample Runbook § Remediation]" in chunks[1].content


def test_chunker_sliding_window_overlap():
    chunker = SectionAwareChunker(chunk_size_words=20, overlap_words=5, inject_headers=True)
    long_text = "word " * 55  # 55 words
    doc = ExtractedDocument(
        title="Long Document",
        raw_content=long_text,
        file_format="markdown",
        sections=[ExtractedSection(title="Section A", content=long_text)],
    )
    chunks = chunker.chunk_document(doc, document_id="doc_long")
    assert len(chunks) > 1
    # Check that chunks retain header
    for c in chunks:
        assert "[Long Document § Section A]" in c.content
        assert c.token_count > 0
