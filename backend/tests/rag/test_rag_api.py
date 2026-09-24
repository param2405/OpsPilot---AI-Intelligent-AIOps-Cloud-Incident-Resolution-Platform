"""API integration tests for RAG endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_list_documents():
    response = client.get("/api/v1/rag/documents")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "documents" in data
    assert data["total"] > 0


def test_api_get_document_detail():
    list_res = client.get("/api/v1/rag/documents")
    first_doc_id = list_res.json()["documents"][0]["id"]

    res = client.get(f"/api/v1/rag/documents/{first_doc_id}")
    assert res.status_code == 200
    doc_data = res.json()
    assert doc_data["id"] == first_doc_id
    assert "raw_content" in doc_data
    assert "chunks" in doc_data
    assert len(doc_data["chunks"]) > 0


def test_api_retrieve():
    payload = {
        "query": "PostgreSQL connection pool HikariCP saturated",
        "top_k": 3,
        "use_reranking": True,
    }
    response = client.post("/api/v1/rag/retrieve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == payload["query"]
    assert len(data["chunks"]) <= 3
    assert len(data["chunks"]) > 0
    assert "score" in data["chunks"][0]


def test_api_query_grounded():
    payload = {
        "query": "How do you detect idle in transaction sessions in PostgreSQL?",
        "top_k": 3,
    }
    response = client.post("/api/v1/rag/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_sufficient_evidence"] is True
    assert "[SOURCE" in data["answer"]
    assert len(data["citations"]) > 0
    assert data["confidence_score"] > 0.2


def test_api_query_unanswerable():
    payload = {
        "query": "How do you configure quantum teleportation entanglement on Azure Quantum?",
        "top_k": 3,
    }
    response = client.post("/api/v1/rag/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_sufficient_evidence"] is False
    assert "insufficient evidence" in data["answer"].lower()


def test_api_ingest_text():
    from app.db.session import SessionLocal
    from app.models.rag import RAGDocument

    doc_id = "doc_temp_test_ingest"
    payload = {
        "document_id": doc_id,
        "title": "Temporary Test Runbook",
        "content": "# Test Runbook\n\n## Remediation\nExecute restart test pod.",
        "document_type": "runbook",
        "service": "test-svc",
        "file_format": "markdown",
    }
    response = client.post("/api/v1/rag/ingest", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["chunks_created"] >= 1

    # Clean up test document
    db = SessionLocal()
    doc = db.get(RAGDocument, doc_id)
    if doc:
        db.delete(doc)
        db.commit()
    db.close()

