"""Unit tests for semantic embeddings and runbook retrieval."""

import numpy as np
import pytest

from app.rag.embeddings.service import LogSemanticEmbeddingService


def test_embedding_dimensions_and_normalization():
    service = LogSemanticEmbeddingService(embedding_dim=128)

    # 1. Single text embedding
    vec = service.embed_text("High CPU utilization on auth-service worker thread")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (128,)
    # L2 norm must be approximately 1.0
    norm = np.linalg.norm(vec)
    assert abs(norm - 1.0) < 1e-4

    # 2. Batch text embedding
    texts = [
        "Normal health check OK",
        "HikariCP connection pool timeout waiting for connection",
        "JVM OutOfMemoryError: Java heap space",
    ]
    batch_vecs = service.embed_batch(texts)
    assert batch_vecs.shape == (3, 128)
    for v in batch_vecs:
        assert abs(np.linalg.norm(v) - 1.0) < 1e-4


def test_semantic_similarity_calculation():
    service = LogSemanticEmbeddingService()

    vec_db1 = service.embed_text("PostgreSQL connection pool timeout HikariCP")
    vec_db2 = service.embed_text("Database connection exhaustion HikariPool timeout")
    vec_jvm = service.embed_text("Java OutOfMemoryError JVM heap exhaustion")

    sim_db_db = service.compute_similarity(vec_db1, vec_db2)
    sim_db_jvm = service.compute_similarity(vec_db1, vec_jvm)

    # Database logs should have higher mutual similarity than Database vs JVM OOM
    assert sim_db_db > sim_db_jvm
    assert -1.0 <= sim_db_db <= 1.0


def test_runbook_retrieval_ranking():
    service = LogSemanticEmbeddingService()

    # Query for database connection exhaustion
    query_db = "HikariPool-1 timeout waiting for idle database connection from pool"
    hits_db = service.search_runbooks(query_db, top_k=3)
    assert len(hits_db) == 3
    # Top ranked runbook should be RB-001 (PostgreSQL Connection Pool)
    assert hits_db[0]["id"] == "RB-001"
    assert "PostgreSQL" in hits_db[0]["title"]
    assert hits_db[0]["rank"] == 1
    assert hits_db[0]["similarity_score"] > hits_db[1]["similarity_score"]

    # Query for JVM OutOfMemoryError
    query_oom = "OutOfMemoryError: Java heap space container killed exit code 137"
    hits_oom = service.search_runbooks(query_oom, top_k=3)
    assert hits_oom[0]["id"] == "RB-002"
    assert "JVM" in hits_oom[0]["title"]
