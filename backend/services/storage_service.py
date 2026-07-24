"""Pluggable file storage for IFPI.

Mirrors the ERP360 storage_service abstraction pattern (LocalStorage /
S3Storage / GCSStorage selected by STORAGE_BACKEND env var) so that IFPI
ships drop-in-compatible with whatever bucket ERP360 eventually adopts —
but stays a fully independent codebase. No imports from ERP360.

Selection (via core.config.settings):
- storage_backend = "local"  →  LocalStorage writes to settings.storage_path
- storage_backend = "s3"     →  S3Storage on settings.s3_bucket (boto3)
- storage_backend = "gcs"    →  GCSStorage on settings.gcs_bucket

In all cases, callers should pass a logical relative key like
"branding/<uuid>.png" and receive back a public URL string suitable to
return to the frontend. The frontend treats the URL opaquely.
"""
from __future__ import annotations

import logging
import mimetypes
import os
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Optional, Union

from core.config import settings

logger = logging.getLogger("ifpi.storage")


class StorageError(Exception):
    """Base exception for storage operations."""


class StorageBackend(ABC):
    @abstractmethod
    def save(self, file: Union[BinaryIO, bytes], path: str,
             content_type: Optional[str] = None) -> str:
        """Persist `file` at `path`. Returns a public URL (or relative path)."""

    @abstractmethod
    def load(self, path: str) -> bytes:
        """Return the bytes at `path`."""

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete `path`. Returns True on success."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Whether `path` exists in this backend."""


class LocalStorage(StorageBackend):
    """Disk-backed storage. Files live under `base_path`. URLs are returned
    as relative paths under `/api/uploads/files/<key>` so the frontend
    resolves them through the same ingress that routes the API."""

    def __init__(self, base_path: str = "./uploads"):
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorage initialized at %s", self.base_path)

    def _full(self, path: str) -> Path:
        target = (self.base_path / path).resolve()
        # Path-traversal guard
        if not str(target).startswith(str(self.base_path)):
            raise StorageError(f"Invalid path: {path}")
        return target

    def save(self, file, path, content_type=None):
        target = self._full(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = file if isinstance(file, (bytes, bytearray)) else file.read()
        target.write_bytes(data)
        logger.info("LocalStorage: wrote %s bytes → %s", len(data), path)
        return f"/api/uploads/files/{path}"

    def load(self, path):
        try:
            return self._full(path).read_bytes()
        except FileNotFoundError as e:
            raise StorageError(f"File not found: {path}") from e

    def delete(self, path):
        try:
            self._full(path).unlink()
            return True
        except FileNotFoundError:
            return False

    def exists(self, path):
        try:
            return self._full(path).exists()
        except StorageError:
            return False


class S3Storage(StorageBackend):
    """Amazon S3 backend. Lazy-loads boto3 so it's not a hard dependency
    until the org actually configures STORAGE_BACKEND=s3."""

    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.bucket = bucket
        self.region = region
        self._client = None
        logger.info("S3Storage configured: s3://%s (%s)", bucket, region)

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3  # type: ignore
            except ImportError as e:
                raise StorageError("boto3 not installed. pip install boto3") from e
            # Optional endpoint override for S3-compatible services
            # (Cloudflare R2, MinIO, etc.). AWS-native ignored when unset.
            endpoint_url = os.environ.get("AWS_S3_ENDPOINT_URL") or None
            self._client = boto3.client(
                "s3", region_name=self.region,
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                endpoint_url=endpoint_url,
            )
        return self._client

    def save(self, file, path, content_type=None):
        body = file if isinstance(file, (bytes, bytearray)) else file.read()
        extra = {}
        guessed = content_type or mimetypes.guess_type(path)[0]
        if guessed:
            extra["ContentType"] = guessed
        self.client.put_object(Bucket=self.bucket, Key=path, Body=body, **extra)
        # Convention: prefer CDN-style public URL when bucket is public-read;
        # for private buckets, callers should mint a presigned URL via load().
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{path}"

    def load(self, path):
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=path)
            return obj["Body"].read()
        except self.client.exceptions.NoSuchKey as e:
            raise StorageError(f"File not found: {path}") from e

    def delete(self, path):
        try:
            self.client.delete_object(Bucket=self.bucket, Key=path)
            return True
        except Exception as e:
            logger.warning("S3 delete failed for %s: %s", path, e)
            return False

    def exists(self, path):
        try:
            self.client.head_object(Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False


class GCSStorage(StorageBackend):
    """Google Cloud Storage backend. Lazy-loaded."""

    def __init__(self, bucket: str, project: Optional[str] = None):
        self.bucket_name = bucket
        self.project = project
        self._client = None
        self._bucket = None

    @property
    def bucket(self):
        if self._bucket is None:
            try:
                from google.cloud import storage as gcs  # type: ignore
            except ImportError as e:
                raise StorageError("google-cloud-storage not installed") from e
            self._client = gcs.Client(project=self.project)
            self._bucket = self._client.bucket(self.bucket_name)
        return self._bucket

    def save(self, file, path, content_type=None):
        blob = self.bucket.blob(path)
        data = file if isinstance(file, (bytes, bytearray)) else file.read()
        blob.upload_from_string(data, content_type=content_type or
                                mimetypes.guess_type(path)[0])
        return f"https://storage.googleapis.com/{self.bucket_name}/{path}"

    def load(self, path):
        blob = self.bucket.blob(path)
        if not blob.exists():
            raise StorageError(f"File not found: {path}")
        return blob.download_as_bytes()

    def delete(self, path):
        try:
            self.bucket.blob(path).delete()
            return True
        except Exception:
            return False

    def exists(self, path):
        return self.bucket.blob(path).exists()


_instance: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    """Singleton accessor honoring the configured STORAGE_BACKEND."""
    global _instance
    if _instance is not None:
        return _instance

    backend = (settings.storage_backend or "local").lower()
    if backend == "s3":
        if not settings.s3_bucket:
            raise StorageError("S3_BUCKET env var required when STORAGE_BACKEND=s3")
        _instance = S3Storage(bucket=settings.s3_bucket, region=settings.s3_region)
    elif backend == "gcs":
        if not settings.gcs_bucket:
            raise StorageError("GCS_BUCKET env var required when STORAGE_BACKEND=gcs")
        _instance = GCSStorage(bucket=settings.gcs_bucket, project=settings.gcs_project)
    else:
        # Default — local disk. Path resolved relative to backend dir.
        base = settings.storage_path
        if not os.path.isabs(base):
            base = str((Path(__file__).parent.parent / base).resolve())
        _instance = LocalStorage(base_path=base)

    return _instance


def reset_storage() -> None:
    """For tests."""
    global _instance
    _instance = None


def to_bytes(maybe_stream: Union[BinaryIO, bytes]) -> bytes:
    """Convenience: normalize a file/bytes input to bytes."""
    if isinstance(maybe_stream, (bytes, bytearray)):
        return bytes(maybe_stream)
    buf = BytesIO()
    buf.write(maybe_stream.read())
    return buf.getvalue()
