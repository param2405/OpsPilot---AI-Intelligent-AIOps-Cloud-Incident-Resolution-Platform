"""Unit tests for RAGEvaluator and benchmark metrics."""

from __future__ import annotations

import pytest
from app.db.session import SessionLocal
from app.rag.evaluation.dataset import EVALUATION_DATASET, EvalSample
from app.rag.evaluation.evaluator import BenchmarkSummary, RAGEvaluator, SampleEvalResult


@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    yield session
    session.close()


def test_evaluator_single_sample(db_session):
    evaluator = RAGEvaluator(db_session)
    sample = EvalSample(
        id="test_sample_01",
        domain="runbooks",
        question="What JVM flags terminate immediately on OutOfMemoryError?",
        expected_source="doc_rb_jvm_oom_recovery",
        expected_information=["-XX:+ExitOnOutOfMemoryError", "HeapDumpPath"],
    )

    result = evaluator.evaluate_sample(sample, top_k=4)
    assert isinstance(result, SampleEvalResult)
    assert result.retrieval_recall == 1.0
    assert result.retrieval_relevance > 0.0
    assert result.answer_faithfulness > 0.7
    assert result.answer_relevance > 0.6
    assert result.has_sufficient_evidence is True


def test_evaluator_unanswerable_sample(db_session):
    evaluator = RAGEvaluator(db_session)
    neg_sample = EvalSample(
        id="test_neg_01",
        domain="unanswerable",
        question="How do you configure quantum teleportation entanglement on Azure?",
        expected_source=None,
        expected_information=[],
        is_answerable=False,
    )

    result = evaluator.evaluate_sample(neg_sample, top_k=4)
    assert result.is_answerable is False
    assert result.has_sufficient_evidence is False
    assert result.answer_faithfulness == 1.0
    assert "insufficient evidence" in result.generated_answer.lower()


def test_evaluator_benchmark_subset(db_session):
    evaluator = RAGEvaluator(db_session)
    # Test on a 3-sample subset for fast regression test
    subset = EVALUATION_DATASET[:3]
    summary = evaluator.evaluate_benchmark(samples=subset, top_k=3)
    assert isinstance(summary, BenchmarkSummary)
    assert summary.total_samples == 3
    assert summary.mean_retrieval_recall == 1.0
    assert summary.mean_answer_faithfulness > 0.8
