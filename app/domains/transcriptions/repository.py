"""
app/domains/transcriptions/repository.py — updated for Phase 6
Adds: version management, get_transcript_history
"""

import uuid
from math import ceil

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domains.transcriptions.models import (
    JobStatus, Transcript, TranscriptionJob, UploadedFile,
)


class TranscriptionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_uploaded_file(
        self, user_id: uuid.UUID, original_filename: str,
        stored_filename: str, file_path: str,
        file_size: int, mime_type: str,
    ) -> UploadedFile:
        f = UploadedFile(
            user_id=user_id, original_filename=original_filename,
            stored_filename=stored_filename, file_path=file_path,
            file_size=file_size, mime_type=mime_type,
        )
        self.db.add(f)
        await self.db.flush()
        return f

    async def create_job(
        self, user_id: uuid.UUID, file_id: uuid.UUID,
        model_size: str, language: str | None,
    ) -> TranscriptionJob:
        job = TranscriptionJob(
            user_id=user_id, file_id=file_id,
            model_size=model_size, language=language,
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
            .options(joinedload(TranscriptionJob.transcripts))
        )
        return result.unique().scalar_one_or_none()

    async def get_job_by_id_admin(
        self, job_id: uuid.UUID
    ) -> TranscriptionJob | None:
        result = await self.db.execute(
            select(TranscriptionJob)
            .where(TranscriptionJob.id == job_id)
            .options(joinedload(TranscriptionJob.transcripts))
        )
        return result.unique().scalar_one_or_none()

    async def list_jobs(
        self, user_id: uuid.UUID, page: int = 1,
        page_size: int = 20, status: JobStatus | None = None,
    ) -> tuple[list[TranscriptionJob], int]:
        query = select(TranscriptionJob).where(
            TranscriptionJob.user_id == user_id
        )
        if status:
            query = query.where(TranscriptionJob.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = (
            query
            .order_by(TranscriptionJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def update_job_status(
        self, job_id: uuid.UUID, status: JobStatus,
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

    async def get_next_version(self, job_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.max(Transcript.version), 0))
            .where(Transcript.job_id == job_id)
        )
        return result.scalar_one() + 1

    async def mark_all_versions_superseded(self, job_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(Transcript).where(Transcript.job_id == job_id)
        )
        for t in result.scalars().all():
            t.is_current = False
        await self.db.flush()

    async def create_transcript(
        self, job_id: uuid.UUID, full_text: str,
        language_detected: str | None, duration_seconds: float | None,
        processing_time_seconds: float | None,
        segments: list | None = None,
        model_size: str = "base",
    ) -> Transcript:
        version = await self.get_next_version(job_id)

        # If re-transcribing, mark old versions as superseded
        if version > 1:
            await self.mark_all_versions_superseded(job_id)

        word_count = len(full_text.split()) if full_text else 0
        t = Transcript(
            job_id=job_id,
            full_text=full_text,
            language_detected=language_detected,
            duration_seconds=duration_seconds,
            processing_time_seconds=processing_time_seconds,
            word_count=word_count,
            segments=segments,
            version=version,
            is_current=True,
            model_size=model_size,
        )
        self.db.add(t)
        await self.db.flush()

        await self.db.execute(
            text(
                "UPDATE transcripts "
                "SET search_vector = to_tsvector('english', full_text) "
                "WHERE id = :id"
            ).bindparams(id=t.id)
        )
        return t

    async def get_transcript_history(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[Transcript]:
        # Verify ownership first
        job = await self.get_job_by_id(job_id, user_id)
        if not job:
            return []

        result = await self.db.execute(
            select(Transcript)
            .where(Transcript.job_id == job_id)
            .order_by(Transcript.version.desc())
        )
        return list(result.scalars().all())

    async def search_transcripts(
        self, user_id: uuid.UUID, query: str,
        page: int = 1, page_size: int = 20,
    ) -> tuple[list[dict], int]:
        search_sql = text("""
            SELECT
                t.id            AS transcript_id,
                tj.id           AS job_id,
                ts_headline(
                    'english', t.full_text,
                    plainto_tsquery('english', :query),
                    'MaxWords=35, MinWords=15, ShortWord=3,
                     HighlightAll=false, MaxFragments=2'
                )               AS snippet,
                t.language_detected,
                t.created_at,
                COUNT(*) OVER() AS total_count
            FROM transcripts t
            JOIN transcription_jobs tj ON tj.id = t.job_id
            WHERE tj.user_id = :user_id
              AND t.is_current = true
              AND t.search_vector @@ plainto_tsquery('english', :query)
            ORDER BY ts_rank(t.search_vector,
                     plainto_tsquery('english', :query)) DESC
            LIMIT  :limit
            OFFSET :offset
        """).bindparams(
            query=query, user_id=user_id,
            limit=page_size, offset=(page - 1) * page_size,
        )

        result = await self.db.execute(search_sql)
        rows = result.mappings().all()
        total = rows[0]["total_count"] if rows else 0
        return [dict(row) for row in rows], total