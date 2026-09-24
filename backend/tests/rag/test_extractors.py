"""Unit tests for multi-format document extractors."""

from __future__ import annotations

import io
import pytest
from app.rag.ingestion.extractors import (
    ExtractedDocument,
    ExtractedSection,
    MarkdownExtractor,
    PDFExtractor,
    PlainTextExtractor,
    get_extractor_for_file,
)


def test_markdown_extractor():
    extractor = MarkdownExtractor()
    sample_md = """# Architecture Overview
This is the system overview.

## Service Decomposition
- Gateway
- Ingestion

## Storage
PostgreSQL and Kafka.
"""
    doc = extractor.extract(sample_md, filename="sample.md")
    assert isinstance(doc, ExtractedDocument)
    assert doc.title == "Architecture Overview"
    assert doc.file_format == "markdown"
    assert len(doc.sections) >= 2

    sec_titles = [s.title for s in doc.sections]
    assert any("Service Decomposition" in t for t in sec_titles)
    assert any("Storage" in t for t in sec_titles)


def test_plaintext_extractor():
    extractor = PlainTextExtractor()
    sample_txt = """Server Log Analysis Guide
Line 1: Check memory.
Line 2: Check CPU.
"""
    doc = extractor.extract(sample_txt, filename="guide.txt")
    assert doc.file_format == "txt"
    assert len(doc.sections) == 1
    assert "Server Log Analysis Guide" in doc.sections[0].content


def test_pdf_extractor():
    extractor = PDFExtractor()
    # Test on the created authentic runbook PDF
    pdf_path = "app/rag/knowledge_base/runbooks/rb_redis_replication_lag.pdf"
    doc = extractor.extract(pdf_path, filename="rb_redis_replication_lag.pdf")
    assert doc.file_format == "pdf"
    assert len(doc.sections) >= 1
    assert "Redis" in doc.raw_content
    assert doc.sections[0].page_number == 1


def test_get_extractor_for_file():
    assert isinstance(get_extractor_for_file("doc.md"), MarkdownExtractor)
    assert isinstance(get_extractor_for_file("doc.txt"), PlainTextExtractor)
    assert isinstance(get_extractor_for_file("doc.pdf"), PDFExtractor)

    with pytest.raises(ValueError):
        get_extractor_for_file("doc.xyz")
