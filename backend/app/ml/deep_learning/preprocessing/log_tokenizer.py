"""Log normalization, template mining, and vocabulary tokenization for deep learning."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Canonical special tokens
PAD_TOKEN = "<PAD>"
UNK_TOKEN = "<UNK>"
SOS_TOKEN = "<SOS>"
EOS_TOKEN = "<EOS>"

PAD_IDX = 0
UNK_IDX = 1
SOS_IDX = 2
EOS_IDX = 3

SPECIAL_TOKENS = [PAD_TOKEN, UNK_TOKEN, SOS_TOKEN, EOS_TOKEN]


class LogNormalizer:
    """Deterministic regex normalizer for stripping dynamic variable entities from raw logs.
    
    Transforms operational log lines (containing volatile metrics, IP addresses, UUIDs,
    and timestamps) into stable, canonical structural templates.
    """

    PATTERNS: List[Tuple[str, str]] = [
        # ISO8601 timestamps and date strings
        (r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?", "<TIME>"),
        (r"\b\d{2}:\d{2}:\d{2}(?:\.\d+)?\b", "<TIME>"),
        # IPv4 and IPv6 addresses with optional port
        (r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b", "<IP>"),
        (r"\b[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{1,4}){7}(?::\d+)?\b", "<IP>"),
        # UUIDs and hex hashes (trace IDs, commit hashes, session IDs)
        (r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "<UUID>"),
        (r"\b[0-9a-fA-F]{16,64}\b", "<HEX>"),
        (r"\b0x[0-9a-fA-F]+\b", "<HEX>"),
        # File paths and URIs
        (r"(?:/[a-zA-Z0-9_\-\.]+){2,}", "<PATH>"),
        (r"(?:[a-zA-Z]:\\[a-zA-Z0-9_\-\.\\]+)", "<PATH>"),
        # Microservice parameter bindings (e.g. svc=auth-service, service="order-service")
        (r"(?:svc|service)=[a-zA-Z0-9_\-]+", "<SVC>"),
        # Quantities, latencies, percentiles, ports, and numeric values
        (r"\b\d+(?:\.\d+)?(?:ms|s|m|MB|GB|KB|kbps|%)?\b", "<NUM>"),
        # Thread identifiers and process IDs
        (r"\b(?:thread|pid|process)[=\s:]+\d+\b", "<THREAD>"),
        # Bracketed or parenthesized numerical sequences
        (r"\[\d+\]|\(\d+\)", "[<NUM>]"),
    ]

    def __init__(self, custom_patterns: Optional[List[Tuple[str, str]]] = None) -> None:
        raw_patterns = self.PATTERNS + (custom_patterns or [])
        self._compiled_regexes = [(re.compile(p, re.IGNORECASE), repl) for p, repl in raw_patterns]
        self._whitespace_re = re.compile(r"\s+")

    def normalize(self, message: str) -> str:
        """Normalize a raw log string by replacing dynamic variables with canonical tokens."""
        if not message:
            return "<EMPTY>"
        
        result = message
        for regex, replacement in self._compiled_regexes:
            result = regex.sub(replacement, result)

        # Collapse whitespace and strip
        result = self._whitespace_re.sub(" ", result).strip()
        return result or "<EMPTY>"

    def __call__(self, message: str) -> str:
        return self.normalize(message)


class LogTemplateMiner:
    """Discovers unique log templates and maps them to canonical Event IDs (e.g. E1, E2, ...)."""

    def __init__(self, normalizer: Optional[LogNormalizer] = None) -> None:
        self.normalizer = normalizer or LogNormalizer()
        self.template_to_event: Dict[str, str] = {}
        self.event_to_template: Dict[str, str] = {}
        self._counter = 0

    def fit(self, messages: Iterable[str]) -> "LogTemplateMiner":
        """Learn unique templates from a collection of raw log messages."""
        for msg in messages:
            self.get_or_create_event_id(msg)
        return self

    def get_or_create_event_id(self, message: str) -> str:
        """Given a raw log message, normalize it and return its canonical Event ID."""
        template = self.normalizer.normalize(message)
        if template not in self.template_to_event:
            self._counter += 1
            event_id = f"E{self._counter}"
            self.template_to_event[template] = event_id
            self.event_to_template[event_id] = template
        return self.template_to_event[template]

    def transform(self, messages: List[str]) -> List[str]:
        """Convert a list of raw log messages into a list of Event IDs."""
        return [self.get_or_create_event_id(msg) for msg in messages]

    @property
    def num_templates(self) -> int:
        return len(self.template_to_event)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_to_event": self.template_to_event,
            "event_to_template": self.event_to_template,
            "counter": self._counter,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogTemplateMiner":
        miner = cls()
        miner.template_to_event = data.get("template_to_event", {})
        miner.event_to_template = data.get("event_to_template", {})
        miner._counter = data.get("counter", len(miner.template_to_event))
        return miner


class LogVocabulary:
    """Vocabulary mapping log events or sub-tokens to integer indices for PyTorch embeddings."""

    def __init__(self, special_tokens: Optional[List[str]] = None) -> None:
        self.special_tokens = special_tokens or SPECIAL_TOKENS.copy()
        self.token_to_idx: Dict[str, int] = {}
        self.idx_to_token: Dict[int, str] = {}
        self._frozen = False

        # Register special tokens first
        for idx, token in enumerate(self.special_tokens):
            self.token_to_idx[token] = idx
            self.idx_to_token[idx] = token

    @property
    def pad_idx(self) -> int:
        return self.token_to_idx.get(PAD_TOKEN, PAD_IDX)

    @property
    def unk_idx(self) -> int:
        return self.token_to_idx.get(UNK_TOKEN, UNK_IDX)

    @property
    def sos_idx(self) -> int:
        return self.token_to_idx.get(SOS_TOKEN, SOS_IDX)

    @property
    def eos_idx(self) -> int:
        return self.token_to_idx.get(EOS_TOKEN, EOS_IDX)

    def add_token(self, token: str) -> int:
        """Add a token to the vocabulary if not present and not frozen."""
        if token in self.token_to_idx:
            return self.token_to_idx[token]
        if self._frozen:
            return self.unk_idx

        new_idx = len(self.token_to_idx)
        self.token_to_idx[token] = new_idx
        self.idx_to_token[new_idx] = token
        return new_idx

    def build_from_tokens(self, token_lists: Iterable[Iterable[str]], min_freq: int = 1) -> "LogVocabulary":
        """Construct vocabulary from tokenized sequences, with minimum frequency cutoff."""
        counts: Dict[str, int] = {}
        for tokens in token_lists:
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1

        for token, count in counts.items():
            if count >= min_freq and token not in self.token_to_idx:
                self.add_token(token)
        return self

    def freeze(self) -> None:
        """Freeze vocabulary so that unknown tokens during inference map to <UNK>."""
        self._frozen = True

    def unfreeze(self) -> None:
        self._frozen = False

    def encode(self, tokens: List[str], add_special: bool = False) -> List[int]:
        """Convert a list of string tokens to integer indices."""
        ids: List[int] = []
        if add_special:
            ids.append(self.sos_idx)
        for token in tokens:
            ids.append(self.token_to_idx.get(token, self.unk_idx))
        if add_special:
            ids.append(self.eos_idx)
        return ids

    def decode(self, ids: List[int], remove_special: bool = True) -> List[str]:
        """Convert integer indices back into string tokens."""
        tokens: List[str] = []
        structural_boundary_tokens = {PAD_TOKEN, SOS_TOKEN, EOS_TOKEN}
        for i in ids:
            tok = self.idx_to_token.get(i, UNK_TOKEN)
            if remove_special and tok in structural_boundary_tokens:
                continue
            tokens.append(tok)
        return tokens

    def pad_or_truncate(self, ids: List[int], max_length: int, pad_value: Optional[int] = None) -> List[int]:
        """Ensure token sequence has exact length max_length via truncation or padding."""
        p_val = self.pad_idx if pad_value is None else pad_value
        if len(ids) > max_length:
            return ids[-max_length:]  # Keep the most recent events
        return ids + [p_val] * (max_length - len(ids))

    def __len__(self) -> int:
        return len(self.token_to_idx)

    def save(self, filepath: str) -> None:
        """Serialize vocabulary configuration to a JSON file."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        payload = {
            "token_to_idx": self.token_to_idx,
            "special_tokens": self.special_tokens,
            "frozen": self._frozen,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        logger.info("Saved LogVocabulary (%d tokens) to %s", len(self), filepath)

    @classmethod
    def load(cls, filepath: str) -> "LogVocabulary":
        """Load vocabulary from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
        vocab = cls(special_tokens=payload.get("special_tokens"))
        vocab.token_to_idx = payload["token_to_idx"]
        vocab.idx_to_token = {int(v): k for k, v in payload["token_to_idx"].items()}
        vocab._frozen = payload.get("frozen", True)
        logger.info("Loaded LogVocabulary (%d tokens) from %s", len(vocab), filepath)
        return vocab
