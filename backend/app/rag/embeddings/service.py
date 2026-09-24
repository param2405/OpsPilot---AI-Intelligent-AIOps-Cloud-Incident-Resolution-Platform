"""Reusable semantic embedding service for logs, historical incidents, and runbooks."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from app.rag.embeddings.sample_runbooks import CANONICAL_RUNBOOKS

logger = logging.getLogger(__name__)


class PyTorchSemanticEncoder(nn.Module):
    """Deterministic, self-contained PyTorch semantic text embedding encoder.
    
    Extracts dense semantic representations using character and subword n-gram hashing
    projected through a non-linear neural compression layer with LayerNorm and L2 unit normalization.
    Ensures zero external dependency on HuggingFace network downloads while delivering
    fast, consistent cosine similarity calculations across observability text.
    """

    def __init__(self, vocab_dim: int = 4096, embedding_dim: int = 128, seed: int = 42) -> None:
        super().__init__()
        self.vocab_dim = vocab_dim
        self.embedding_dim = embedding_dim

        torch.manual_seed(seed)
        self.embedding = nn.Embedding(vocab_dim, 64)
        self.fc = nn.Sequential(
            nn.Linear(64, embedding_dim),
            nn.LayerNorm(embedding_dim),
            nn.Tanh(),
            nn.Linear(embedding_dim, embedding_dim),
        )
        self.eval()

    def _tokenize_to_hashes(self, text: str) -> List[int]:
        """Convert text into token & character trigram hash buckets."""
        words = text.lower().replace("-", " ").replace("_", " ").split()
        hashes: List[int] = []
        for word in words:
            # Word hash
            h_word = int(hashlib.md5(word.encode("utf-8")).hexdigest()[:8], 16) % self.vocab_dim
            hashes.append(h_word)
            # Subword 3-grams
            if len(word) >= 3:
                for j in range(len(word) - 2):
                    trigram = word[j : j + 3]
                    h_tri = int(hashlib.md5(trigram.encode("utf-8")).hexdigest()[:8], 16) % self.vocab_dim
                    hashes.append(h_tri)
        return hashes or [0]

    def forward(self, texts: List[str]) -> torch.Tensor:
        """Encode list of strings into L2-normalized dense embeddings [Batch, EmbeddingDim]."""
        with torch.no_grad():
            batch_vectors: List[torch.Tensor] = []
            for text in texts:
                hash_ids = torch.tensor(self._tokenize_to_hashes(text), dtype=torch.long)
                # Mean pool word and character token embeddings
                token_embeds = self.embedding(hash_ids)  # [NumHashes, 64]
                pooled = token_embeds.mean(dim=0, keepdim=True)  # [1, 64]
                # Project through dense layer
                dense = self.fc(pooled)  # [1, EmbeddingDim]
                # L2 normalize
                normed = F.normalize(dense, p=2, dim=-1)
                batch_vectors.append(normed)
            return torch.cat(batch_vectors, dim=0)


class LogSemanticEmbeddingService:
    """Enterprise-grade semantic embedding and retrieval service for OpsPilot AI.
    
    Powers semantic similarity between:
      1. Incoming operational error logs
      2. Historical postmortem descriptions
      3. SRE troubleshooting runbooks
    Prepares the modular foundation for future Retrieval-Augmented Generation (RAG).
    """

    def __init__(
        self,
        provider: str = "pytorch_dense",
        model_name: str = "all-MiniLM-L6-v2",
        embedding_dim: int = 128,
    ) -> None:
        self.provider = provider
        self.model_name = model_name
        self.embedding_dim = embedding_dim
        self._hf_model = None

        if provider == "sentence_transformers":
            try:
                from sentence_transformers import SentenceTransformer
                self._hf_model = SentenceTransformer(model_name)
                logger.info("Loaded SentenceTransformer model '%s'", model_name)
            except Exception as exc:
                logger.warning(
                    "sentence-transformers not available or model load failed (%s); falling back to PyTorchSemanticEncoder",
                    exc,
                )
                self.provider = "pytorch_dense"

        if self.provider == "pytorch_dense":
            self._pytorch_encoder = PyTorchSemanticEncoder(embedding_dim=embedding_dim)
            logger.info("Initialized PyTorchSemanticEncoder (embedding_dim=%d)", embedding_dim)

        # Pre-cache canonical runbook embeddings
        self._cached_runbooks = CANONICAL_RUNBOOKS
        self._runbook_embeddings = self._embed_corpus_field(self._cached_runbooks, field="symptoms")

    def _embed_corpus_field(self, corpus: List[Dict[str, Any]], field: str) -> np.ndarray:
        texts = [f"{item.get('title', '')} {item.get(field, '')}" for item in corpus]
        return self.embed_batch(texts)

    def embed_text(self, text: str) -> np.ndarray:
        """Encode a single text string into a 1D unit-normalized float32 numpy array."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Encode a batch of text strings into a 2D [N, Dim] unit-normalized float32 numpy array."""
        if not texts:
            return np.empty((0, self.embedding_dim), dtype=np.float32)

        if self._hf_model is not None:
            embeddings = self._hf_model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            return embeddings.astype(np.float32)

        # PyTorch fallback encoder
        with torch.no_grad():
            tensor = self._pytorch_encoder(texts)
            return tensor.cpu().numpy().astype(np.float32)

    @staticmethod
    def compute_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two unit-normalized embedding vectors."""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def find_top_k_similar(
        self,
        query: str,
        corpus: List[Dict[str, Any]],
        text_field: str = "symptoms",
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Find the top-K most semantically similar documents in a corpus for a given query text."""
        if not corpus:
            return []

        query_vec = self.embed_text(query)
        corpus_texts = [f"{item.get('title', '')} {item.get(text_field, '')}" for item in corpus]
        corpus_vecs = self.embed_batch(corpus_texts)

        # Cosine similarity matrix multiplication
        similarities = np.dot(corpus_vecs, query_vec)
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results: List[Dict[str, Any]] = []
        for rank, idx in enumerate(top_indices, start=1):
            score = float(similarities[idx])
            item = dict(corpus[idx])
            item["similarity_score"] = round(score, 4)
            item["rank"] = rank
            results.append(item)

        return results

    def search_runbooks(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Find the most relevant remediation runbooks for an error log or symptom description."""
        query_vec = self.embed_text(query)
        similarities = np.dot(self._runbook_embeddings, query_vec)
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results: List[Dict[str, Any]] = []
        for rank, idx in enumerate(top_indices, start=1):
            rb = dict(self._cached_runbooks[idx])
            rb["similarity_score"] = round(float(similarities[idx]), 4)
            rb["rank"] = rank
            results.append(rb)
        return results

    def search_historical_incidents(
        self,
        query: str,
        incidents: List[Dict[str, Any]],
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Find past historical incidents with symptoms matching the query log sequence."""
        return self.find_top_k_similar(query, incidents, text_field="symptoms", top_k=top_k)
