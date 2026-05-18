"""
app/storage/factory.py

Returns the correct storage backend based on STORAGE_BACKEND env var.
Service layer imports from here — never from local.py or s3.py directly.
Switching from local to S3 = change one env var.
"""

from typing import Callable

from app.core.config import settings


def get_save_fn() -> Callable:
    if settings.storage_backend == "s3":
        from app.storage.s3 import save_upload_s3
        return save_upload_s3
    from app.storage.local import save_upload
    return save_upload


def get_delete_fn() -> Callable:
    if settings.storage_backend == "s3":
        from app.storage.s3 import delete_file_s3
        return delete_file_s3
    from app.storage.local import delete_file
    return delete_file


def get_filename_generator() -> Callable:
    if settings.storage_backend == "s3":
        from app.storage.s3 import generate_stored_filename
        return generate_stored_filename
    from app.storage.local import generate_stored_filename
    return generate_stored_filename