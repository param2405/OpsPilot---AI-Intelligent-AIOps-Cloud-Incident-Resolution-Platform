"""AWS S3 Object Storage Service for OpsPilot AI.

Manages durable cloud storage for:
- RAG runbooks and knowledge base documents
- ML model binaries and scaler artifacts
- Incident diagnostic captures and postmortem reports

Falls back to local file storage when running offline or in development environments
without an S3 bucket configured.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class S3ArtifactStorageService:
    """Enterprise artifact storage service supporting AWS S3 with local disk fallback."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        local_fallback_dir: str = "data/artifacts",
    ) -> None:
        self.settings = get_settings()
        self.bucket_name = bucket_name or self.settings.s3_artifact_bucket
        self.region_name = region_name or self.settings.aws_region
        self.endpoint_url = endpoint_url or self.settings.s3_endpoint_url
        self.local_fallback_dir = Path(local_fallback_dir)
        self._s3_client: Optional[Any] = None
        self._initialized = False

    def _get_client(self) -> Optional[Any]:
        """Lazy-initialize boto3 S3 client if configured."""
        if not self._initialized:
            self._initialized = True
            if not self.bucket_name:
                logger.info(
                    "S3_ARTIFACT_BUCKET is not set; using local filesystem storage at %s",
                    self.local_fallback_dir,
                )
                return None

            try:
                import boto3

                client_kwargs: Dict[str, Any] = {"region_name": self.region_name}
                if self.endpoint_url:
                    client_kwargs["endpoint_url"] = self.endpoint_url

                self._s3_client = boto3.client("s3", **client_kwargs)
                logger.info(
                    "Initialized AWS S3 storage client for bucket '%s' (region: %s)",
                    self.bucket_name,
                    self.region_name,
                )
            except ImportError:
                logger.warning("boto3 is not installed; falling back to local storage.")
                self._s3_client = None
            except Exception as exc:
                logger.warning("Failed to initialize boto3 S3 client: %s; using local storage", exc)
                self._s3_client = None

        return self._s3_client

    @property
    def is_s3_enabled(self) -> bool:
        """Returns True if actively communicating with AWS S3."""
        return self._get_client() is not None and bool(self.bucket_name)

    def upload_bytes(
        self,
        data: bytes,
        s3_key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload raw bytes to S3 or local fallback storage. Returns URI or relative path."""
        clean_key = s3_key.lstrip("/")
        client = self._get_client()

        if client and self.bucket_name:
            extra_args: Dict[str, Any] = {"ContentType": content_type}
            if metadata:
                extra_args["Metadata"] = metadata

            client.put_object(
                Bucket=self.bucket_name,
                Key=clean_key,
                Body=data,
                **extra_args,
            )
            uri = f"s3://{self.bucket_name}/{clean_key}"
            logger.debug("Uploaded %d bytes to %s", len(data), uri)
            return uri
        else:
            local_target = self.local_fallback_dir / clean_key
            local_target.parent.mkdir(parents=True, exist_ok=True)
            local_target.write_bytes(data)
            logger.debug("Stored %d bytes to local fallback %s", len(data), local_target)
            return str(local_target)

    def upload_file(
        self,
        local_path: str | Path,
        s3_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload a file on disk to S3 or copy to local fallback directory."""
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(f"File to upload not found: {local_path}")

        data = path.read_bytes()
        return self.upload_bytes(data, s3_key, content_type or "application/octet-stream", metadata)

    def get_bytes(self, s3_key: str) -> bytes:
        """Fetch bytes from S3 or local fallback storage."""
        clean_key = s3_key.lstrip("/")
        client = self._get_client()

        if client and self.bucket_name:
            response = client.get_object(Bucket=self.bucket_name, Key=clean_key)
            return response["Body"].read()
        else:
            local_target = self.local_fallback_dir / clean_key
            if not local_target.exists():
                raise FileNotFoundError(f"Artifact not found in local storage: {clean_key}")
            return local_target.read_bytes()

    def list_objects(self, prefix: str = "") -> List[str]:
        """List object keys under given prefix."""
        clean_prefix = prefix.lstrip("/")
        client = self._get_client()

        if client and self.bucket_name:
            paginator = client.get_paginator("list_objects_v2")
            keys: List[str] = []
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=clean_prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys
        else:
            base = self.local_fallback_dir / clean_prefix
            if not base.exists():
                return []
            if base.is_file():
                return [clean_prefix]
            return [str(p.relative_to(self.local_fallback_dir)).replace("\\", "/") for p in base.rglob("*") if p.is_file()]

    def delete_object(self, s3_key: str) -> bool:
        """Delete object from S3 or local storage."""
        clean_key = s3_key.lstrip("/")
        client = self._get_client()

        if client and self.bucket_name:
            client.delete_object(Bucket=self.bucket_name, Key=clean_key)
            return True
        else:
            local_target = self.local_fallback_dir / clean_key
            if local_target.exists():
                local_target.unlink()
                return True
            return False
