"""MinIO object storage — encrypted media upload with auto-purge."""
from __future__ import annotations
import asyncio
import hashlib
import io
import json
import uuid
from datetime import datetime, timezone, timedelta

from minio import Minio
from minio.error import S3Error
from minio.commonconfig import ENABLED, Filter
from minio.lifecycleconfig import LifecycleConfig, Rule, Expiration

from config import settings

_client: Minio | None = None


def _get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        # Ensure bucket exists
        if not _client.bucket_exists(settings.minio_bucket):
            _client.make_bucket(settings.minio_bucket)
            # Lifecycle: auto-delete objects after retention period
            _client.set_bucket_lifecycle(
                settings.minio_bucket,
                LifecycleConfig([Rule(
                    ENABLED, rule_filter=Filter(prefix="media/"),
                    rule_id="auto-purge",
                    expiration=Expiration(days=1),
                )]),
            )
    return _client


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def upload_media(
    data: bytes,
    content_type: str,
    assessment_id: str,
    media_type: str,   # "document" | "selfie"
) -> tuple[str, str]:
    """
    Upload encrypted media, return (object_key, sha256_hash).
    Actual encryption is via MinIO server-side SSE or pre-encrypted bytes.
    Returns only the hash to the caller — raw bytes are never stored in DB.
    """
    sha = _sha256_hex(data)
    key = f"media/{assessment_id}/{media_type}/{uuid.uuid4().hex}"

    def _upload():
        client = _get_client()
        client.put_object(
            settings.minio_bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
            metadata={
                "x-amz-meta-assessment": assessment_id,
                "x-amz-meta-sha256": sha,
                "x-amz-meta-uploaded": datetime.now(timezone.utc).isoformat(),
            },
        )

    await asyncio.get_event_loop().run_in_executor(None, _upload)
    return key, sha


async def get_media(object_key: str) -> bytes:
    def _get():
        client = _get_client()
        resp = client.get_object(settings.minio_bucket, object_key)
        data = resp.read()
        resp.close()
        return data
    return await asyncio.get_event_loop().run_in_executor(None, _get)


async def delete_media(object_key: str) -> None:
    def _del():
        client = _get_client()
        client.remove_object(settings.minio_bucket, object_key)
    await asyncio.get_event_loop().run_in_executor(None, _del)


async def purge_expired_media() -> int:
    """Delete media objects older than media_retention_hours. Called by Celery beat."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.media_retention_hours)
    deleted = 0

    def _purge():
        nonlocal deleted
        client = _get_client()
        objects = client.list_objects(settings.minio_bucket, prefix="media/", recursive=True)
        for obj in objects:
            if obj.last_modified and obj.last_modified < cutoff:
                client.remove_object(settings.minio_bucket, obj.object_name)
                deleted += 1

    await asyncio.get_event_loop().run_in_executor(None, _purge)
    return deleted
