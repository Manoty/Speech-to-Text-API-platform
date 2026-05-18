"""
app/domains/transcriptions/repository.py
"""

import uuid
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.transcriptions.models import (
    JobStatus,
    Transcript,
    TranscriptionJob,
    UploadedFile,
)


class TranscriptionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_uploaded_file(
        self,
        user_id: uuid.UUID,
        original_filename: str,
        stored_filename: str,
        file_path: str,
        file_size: int,
        mime_type: str,
    ) -> UploadedFile:
        f = UploadedFile(
            user_id=user_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
        )
        self.db.add(f)
        await self.db.flush()
        return f

    async def create_job(
        self,
        user_id: uuid.UUID,
        file_id: uuid.UUID,
        model_size: str,
        language: str | None,
    ) -> TranscriptionJob:
        job = TranscriptionJob(
            user_id=user_id,
            file_id=file_id,
            model_size=model_size,
            language=language,
            status=JobStatus.PENDING,
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def get_job_by_id(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> TranscriptionJob | None:
        result = await self.db.execute(
            select(TranscriptionJob)
            .where(
                TranscriptionJob.id == job_id,
                TranscriptionJob.user_id == user_id,
            )
            .options(selectinload(TranscriptionJob.transcript))
        )
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: JobStatus | None = None,
    ) -> tuple[list[TranscriptionJob], int]:
        query = select(TranscriptionJob).where(TranscriptionJob.user_id == user_id)

        if status:
            query = query.where(TranscriptionJob.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(TranscriptionJob.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        return result.scalars().all(), total  # type: ignore[return-value]

    async def update_job_status(
        self,
        job_id: uuid.UUID,
        status: JobStatus,
        error_message: str | None = None,
        celery_task_id: str | None = None,
    ) -> None:
        result = await self.db.execute(
            select(TranscriptionJob).where(TranscriptionJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job:
            job.status = status
            if error_message is not None:
                job.error_message = error_message
            if celery_task_id is not None:
                job.celery_task_id = celery_task_id
            await self.db.flush()

    async def create_transcript(
        self,
        job_id: uuid.UUID,
        full_text: str,
        language_detected: str | None,
        duration_seconds: float | None,
        processing_time_seconds: float | None,
    ) -> Transcript:
        word_count = len(full_text.split()) if full_text else 0
        t = Transcript(
            job_id=job_id,
            full_text=full_text,
            language_detected=language_detected,
            duration_seconds=duration_seconds,
            processing_time_seconds=processing_time_seconds,
            word_count=word_count,
        )
        self.db.add(t)
        await self.db.flush()
        return t