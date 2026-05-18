"""
app/storage/local.py

Local filesystem storage. Designed with an interface that
mirrors what an S3 adapter would look like in Phase 3.
"""

import uuid
from pathlib import Path

import aiofiles

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ALLOWED_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
    "audio/flac",
    "video/mp4",
    "video/webm",
    "video/quicktime",
}


def get_upload_path() -> Path:
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_stored_filename(original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower()
    return f"{uuid.uuid4()}{suffix}"


async def save_upload(file_bytes: bytes, stored_filename: str) -> str:
    """Save bytes to disk, return absolute path."""
    file_path = get_upload_path() / stored_filename
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_bytes)
    logger.info("file_saved", path=str(file_path), size=len(file_bytes))
    return str(file_path)


async def delete_file(file_path: str) -> None:
    path = Path(file_path)
    if path.exists():
        path.unlink()
        logger.info("file_deleted", path=file_path)