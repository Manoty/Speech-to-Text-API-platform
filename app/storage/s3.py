"""
app/storage/s3.py

S3-compatible storage using boto3.
Works with AWS S3 and MinIO (same API).

WHY MinIO locally?
- Identical API to AWS S3
- Runs in Docker, zero cost
- Production switch = just change env vars
"""

import uuid
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


def generate_stored_filename(original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower()
    return f"{uuid.uuid4()}{suffix}"


async def save_upload_s3(file_bytes: bytes, stored_filename: str) -> str:
    """Upload to S3/MinIO, return the object key as the 'path'."""
    client = _get_client()
    key = f"uploads/{stored_filename}"

    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=file_bytes,
        ContentLength=len(file_bytes),
    )

    logger.info("s3_upload_complete", key=key, size=len(file_bytes))
    return key  # returned as file_path, worker uses this to download


async def get_download_url(key: str, expires: int = 3600) -> str:
    """Generate a pre-signed URL for temporary access."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires,
    )


async def delete_file_s3(key: str) -> None:
    client = _get_client()
    client.delete_object(Bucket=settings.s3_bucket, Key=key)
    logger.info("s3_file_deleted", key=key)