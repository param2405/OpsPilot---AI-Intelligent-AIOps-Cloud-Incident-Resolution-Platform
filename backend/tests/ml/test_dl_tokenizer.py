"""Unit tests for LogNormalizer, LogTemplateMiner, and LogVocabulary."""

import os
import tempfile
import pytest

from app.ml.deep_learning.preprocessing.log_tokenizer import (
    EOS_IDX,
    EOS_TOKEN,
    PAD_IDX,
    PAD_TOKEN,
    SOS_IDX,
    SOS_TOKEN,
    UNK_IDX,
    UNK_TOKEN,
    LogNormalizer,
    LogTemplateMiner,
    LogVocabulary,
)


def test_log_normalizer_masks_dynamic_entities():
    normalizer = LogNormalizer()

    # IP address masking
    msg_ip = "Failed connection to 192.168.1.104:5432 after timeout"
    norm_ip = normalizer.normalize(msg_ip)
    assert "<IP>" in norm_ip
    assert "192.168.1.104" not in norm_ip

    # UUID and Hex masking
    msg_uuid = "Trace 4a12b890-5f21-4a11-b012-9c123456789a terminated at 0x7fff56a1b2"
    norm_uuid = normalizer.normalize(msg_uuid)
    assert "<UUID>" in norm_uuid
    assert "<HEX>" in norm_uuid
    assert "4a12b890" not in norm_uuid

    # Numbers and Latencies
    msg_num = "Query elapsed 4250ms with 98% CPU load"
    norm_num = normalizer.normalize(msg_num)
    assert "<NUM>" in norm_num

    # Timestamps
    msg_ts = "2026-09-24T10:15:30Z Worker thread hung"
    norm_ts = normalizer.normalize(msg_ts)
    assert "<TIME>" in norm_ts

    # Empty string edge case
    assert normalizer.normalize("") == "<EMPTY>"


def test_log_template_miner():
    miner = LogTemplateMiner()

    logs = [
        "Timeout waiting for database connection pool HikariPool-1 (timeout=5000ms)",
        "Timeout waiting for database connection pool HikariPool-2 (timeout=3000ms)",
        "java.lang.OutOfMemoryError: Java heap space. Container killed.",
    ]

    event_ids = miner.transform(logs)
    assert len(event_ids) == 3
    # The first two logs share the same structural template
    assert event_ids[0] == event_ids[1]
    # The third log has a different template
    assert event_ids[0] != event_ids[2]
    assert miner.num_templates == 2

    # Verify serialization
    data = miner.to_dict()
    reconstructed = LogTemplateMiner.from_dict(data)
    assert reconstructed.num_templates == 2
    assert reconstructed.transform([logs[0]]) == [event_ids[0]]


def test_log_vocabulary_encoding_decoding():
    vocab = LogVocabulary()
    assert len(vocab) == 4  # PAD, UNK, SOS, EOS
    assert vocab.pad_idx == PAD_IDX
    assert vocab.unk_idx == UNK_IDX

    # Add tokens
    idx1 = vocab.add_token("E1")
    idx2 = vocab.add_token("E2")
    assert idx1 == 4
    assert idx2 == 5

    # Encode with special tokens
    encoded = vocab.encode(["E1", "E2", "E_UNSEEN"], add_special=True)
    assert encoded[0] == SOS_IDX
    assert encoded[1] == idx1
    assert encoded[2] == idx2
    assert encoded[3] == UNK_IDX  # Unseen token maps to UNK
    assert encoded[4] == EOS_IDX

    # Decode
    decoded = vocab.decode(encoded, remove_special=True)
    assert decoded == ["E1", "E2", UNK_TOKEN]

    # Pad or truncate
    padded = vocab.pad_or_truncate([idx1, idx2], max_length=5)
    assert len(padded) == 5
    assert padded == [idx1, idx2, PAD_IDX, PAD_IDX, PAD_IDX]

    truncated = vocab.pad_or_truncate([1, 2, 3, 4, 5, 6], max_length=3)
    assert len(truncated) == 3
    assert truncated == [4, 5, 6]


def test_log_vocabulary_save_and_load():
    vocab = LogVocabulary()
    vocab.add_token("E1")
    vocab.add_token("E2")
    vocab.freeze()

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "vocab.json")
        vocab.save(path)

        loaded = LogVocabulary.load(path)
        assert len(loaded) == len(vocab)
        assert loaded.encode(["E1", "E2"]) == vocab.encode(["E1", "E2"])
        assert loaded.encode(["UNSEEN"]) == [UNK_IDX]
