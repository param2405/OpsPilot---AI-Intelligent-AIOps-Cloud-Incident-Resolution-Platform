"""Tests for S3ArtifactStorageService."""

from pathlib import Path
import pytest
from app.services.s3_storage_service import S3ArtifactStorageService


def test_s3_storage_local_fallback(tmp_path: Path) -> None:
    """Verify local fallback storage works seamlessly when no S3 bucket is configured."""
    storage = S3ArtifactStorageService(
        bucket_name=None,
        local_fallback_dir=str(tmp_path / "artifacts"),
    )

    assert not storage.is_s3_enabled

    # Test upload bytes
    test_content = b"OpsPilot Incident Report #1042"
    key = "incidents/2026/report_1042.txt"
    target = storage.upload_bytes(test_content, key)

    assert Path(target).exists()

    # Test get bytes
    retrieved = storage.get_bytes(key)
    assert retrieved == test_content

    # Test list objects
    items = storage.list_objects("incidents")
    assert len(items) == 1
    assert "report_1042.txt" in items[0]

    # Test delete
    assert storage.delete_object(key) is True
    assert not Path(target).exists()


def test_s3_storage_upload_file(tmp_path: Path) -> None:
    """Verify uploading a local file copies it to local fallback storage correctly."""
    source_file = tmp_path / "runbook_jvm.md"
    source_file.write_text("# JVM Runbook Guide", encoding="utf-8")

    storage = S3ArtifactStorageService(
        bucket_name=None,
        local_fallback_dir=str(tmp_path / "artifacts"),
    )

    key = "runbooks/jvm.md"
    result = storage.upload_file(source_file, key)
    assert Path(result).exists()
    assert storage.get_bytes(key) == b"# JVM Runbook Guide"
