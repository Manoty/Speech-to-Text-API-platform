"""
app/domains/transcriptions/service.py — updated for Phase 6
Adds: re-transcribe, version history, magic byte validation
"""

import uuid
from math import ceil

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache
from app.core.config import settings
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError, NotFoundError
from app.core.logging import get_logger
from app.domains.quotas.service import QuotaService
from app.domains.transcriptions.export import generate_srt, generate_txt, generate_vtt
from app.domains.transcriptions.models import JobStatus
from app.domains.transcriptions.repository import TranscriptionRepository
from app.domains.transcriptions.schemas import (
    JobDetailResponse, PaginatedJobsResponse, SearchResponse,
    TranscriptHistoryResponse, TranscriptSearchResult,
    TranscriptionJobResponse, TranscriptResponse,
)
from app.storage.factory import get_filename_generator, get_save_fn
from app.storage.local import ALLOWED_MIME_TYPES
from app.storage.validation import sanitize_filename, validate_file_magic

logger = get_logger(__name__)


class TranscriptionService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = TranscriptionRepository(db)
        self.quota_service = QuotaService(db)

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

        # Deep validation — magic bytes
        validate_file_magic(file_bytes, file.filename or "upload")

        await self.quota_service.check_and_reserve(
            user_id=user_id, estimated_minutes=10.0
        )

        generate_filename = get_filename_generator()
        save_file = get_save_fn()
        safe_name = sanitize_filename(file.filename or "upload")
        stored_filename = generate_filename(safe_name)
        file_path = await save_file(file_bytes, stored_filename)
        effective_model = model_size or settings.whisper_model_size

        uploaded_file = await self.repo.create_uploaded_file(
            user_id=user_id,
            original_filename=safe_name,
            stored_filename=stored_filename,
            file_path=file_path,
            file_size=len(file_bytes),
            mime_type=file.content_type or "application/octet-stream",
        )

        job = await self.repo.create_job(
            user_id=user_id, file_id=uploaded_file.id,
            model_size=effective_model, language=language,
        )

        from app.domains.transcriptions.tasks import transcribe_audio
        task = transcribe_audio.delay(
            job_id=str(job.id), file_path=file_path,
            language=language, model_size=effective_model,
            user_id=str(user_id),
        )

        await self.repo.update_job_status(
            job_id=job.id, status=JobStatus.PENDING,
            celery_task_id=task.id,
        )
        await cache.invalidate_job(str(job.id))

        logger.info("job_created", job_id=str(job.id), user_id=str(user_id))
        return TranscriptionJobResponse.model_validate(job)

    async def retranscribe(
        self,
        job_id: uuid.UUID,
        user_id: uuid.UUID,
        model_size: str,
        language: str | None,
    ) -> TranscriptionJobResponse:
        """
        Re-submit an existing job with a different model or language.
        Previous transcript is preserved as an older version.
        """
        job = await self.repo.get_job_by_id(job_id, user_id)
        if not job:
            raise NotFoundError("Transcription job")

        # Reset job status to pending
        await self.repo.update_job_status(job_id=job.id, status=JobStatus.PENDING)

        from app.domains.transcriptions.tasks import transcribe_audio
        task = transcribe_audio.delay(
            job_id=str(job.id),
            file_path=job.uploaded_file.file_path,
            language=language,
            model_size=model_size,
            user_id=str(user_id),
        )

        await self.repo.update_job_status(
            job_id=job.id, status=JobStatus.PENDING,
            celery_task_id=task.id,
        )
        await cache.invalidate_job(str(job.id))

        logger.info(
            "job_retranscribe_queued",
            job_id=str(job.id),
            model_size=model_size,
        )
        return TranscriptionJobResponse.model_validate(job)

    async def get_transcript_history(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> TranscriptHistoryResponse:
        versions = await self.repo.get_transcript_history(job_id, user_id)
        if not versions:
            raise NotFoundError("Transcription job or transcript")
        return TranscriptHistoryResponse(
            job_id=job_id,
            versions=[TranscriptResponse.model_validate(v) for v in versions],
            total_versions=len(versions),
        )

    async def get_job(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> JobDetailResponse:
        job_id_str = str(job_id)
        cached = await cache.get_transcript(job_id_str)
        if cached:
            return JobDetailResponse(**cached)

        job = await self.repo.get_job_by_id(job_id, user_id)
        if not job:
            raise NotFoundError("Transcription job")

        result = JobDetailResponse(
            job=TranscriptionJobResponse.model_validate(job),
            transcript=TranscriptResponse.model_validate(job.transcript)
            if job.transcript else None,
        )

        if job.status == JobStatus.COMPLETED and job.transcript:
            await cache.set_transcript(job_id_str, result.model_dump())

        return result

    async def list_jobs(
        self, user_id: uuid.UUID, page: int = 1,
        page_size: int = 20, status: JobStatus | None = None,
    ) -> PaginatedJobsResponse:
        jobs, total = await self.repo.list_jobs(
            user_id=user_id, page=page, page_size=page_size, status=status
        )
        return PaginatedJobsResponse(
            items=[TranscriptionJobResponse.model_validate(j) for j in jobs],
            total=total, page=page, page_size=page_size,
            pages=ceil(total / page_size) if total else 0,
        )

    async def search(
        self, user_id: uuid.UUID, query: str,
        page: int = 1, page_size: int = 20,
    ) -> SearchResponse:
        rows, total = await self.repo.search_transcripts(
            user_id=user_id, query=query, page=page, page_size=page_size
        )
        items = [
            TranscriptSearchResult(
                job_id=row["job_id"],
                transcript_id=row["transcript_id"],
                snippet=row["snippet"],
                language_detected=row["language_detected"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
        return SearchResponse(items=items, total=total, query=query)

    async def export(
        self, job_id: uuid.UUID, user_id: uuid.UUID, format: str,
    ) -> tuple[str, str, str]:
        job = await self.repo.get_job_by_id(job_id, user_id)
        if not job:
            raise NotFoundError("Transcription job")
        if not job.transcript:
            raise NotFoundError("Transcript not ready yet")

        transcript = job.transcript
        if format == "srt":
            return generate_srt(transcript), "text/plain", f"transcript_{job_id}.srt"
        elif format == "vtt":
            return generate_vtt(transcript), "text/vtt", f"transcript_{job_id}.vtt"
        else:
            return generate_txt(transcript), "text/plain", f"transcript_{job_id}.txt"