"""
app/domains/transcriptions/service.py — updated for Phase 3
"""

import uuid
from math import ceil

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError, NotFoundError
from app.core.logging import get_logger
from app.domains.transcriptions.models import JobStatus
from app.domains.transcriptions.repository import TranscriptionRepository
from app.domains.transcriptions.schemas import (
    JobDetailResponse,
    PaginatedJobsResponse,
    TranscriptionJobResponse,
    TranscriptResponse,
)
from app.storage.factory import get_delete_fn, get_filename_generator, get_save_fn
from app.storage.local import ALLOWED_MIME_TYPES

logger = get_logger(__name__)


class TranscriptionService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = TranscriptionRepository(db)

    async def upload_and_create_job(
        self,
        user_id: uuid.UUID,
        file: UploadFile,
        language: str | None = None,
        model_size: str | None = None,
    ) -> TranscriptionJobResponse:
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise InvalidFileTypeError(list(ALLOWED_MIME_TYPES))

        file_bytes = await file.read()
        if len(file_bytes) > settings.max_file_size_bytes:
            raise FileTooLargeError(settings.max_file_size_mb)

        generate_filename = get_filename_generator()
        save_file = get_save_fn()

        stored_filename = generate_filename(file.filename or "upload")
        file_path = await save_file(file_bytes, stored_filename)

        effective_model = model_size or settings.whisper_model_size

        uploaded_file = await self.repo.create_uploaded_file(
            user_id=user_id,
            original_filename=file.filename or "upload",
            stored_filename=stored_filename,
            file_path=file_path,
            file_size=len(file_bytes),
            mime_type=file.content_type or "application/octet-stream",
        )

        job = await self.repo.create_job(
            user_id=user_id,
            file_id=uploaded_file.id,
            model_size=effective_model,
            language=language,
        )

        from app.domains.transcriptions.tasks import transcribe_audio
        task = transcribe_audio.delay(
            job_id=str(job.id),
            file_path=file_path,
            language=language,
            model_size=effective_model,
            user_id=str(user_id),       # ← new in Phase 3
        )

        await self.repo.update_job_status(
            job_id=job.id,
            status=JobStatus.PENDING,
            celery_task_id=task.id,
        )

        logger.info("job_created", job_id=str(job.id), user_id=str(user_id))
        return TranscriptionJobResponse.model_validate(job)

    async def get_job(self, job_id: uuid.UUID, user_id: uuid.UUID) -> JobDetailResponse:
        job = await self.repo.get_job_by_id(job_id, user_id)
        if not job:
            raise NotFoundError("Transcription job")
        return JobDetailResponse(
            job=TranscriptionJobResponse.model_validate(job),
            transcript=TranscriptResponse.model_validate(job.transcript) if job.transcript else None,
        )

    async def list_jobs(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: JobStatus | None = None,
    ) -> PaginatedJobsResponse:
        jobs, total = await self.repo.list_jobs(
            user_id=user_id, page=page, page_size=page_size, status=status
        )
        return PaginatedJobsResponse(
            items=[TranscriptionJobResponse.model_validate(j) for j in jobs],
            total=total,
            page=page,
            page_size=page_size,
            pages=ceil(total / page_size) if total else 0,
        )