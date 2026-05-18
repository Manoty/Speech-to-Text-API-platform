"""
app/domains/transcriptions/tasks.py

Celery task that runs faster-whisper transcription.

WHY sync task (not async)?
Celery workers are sync by default. faster-whisper is a
blocking CPU/GPU call — running it in a sync worker is correct.
For async Celery, you'd need celery[gevent] which adds complexity.
"""

import time
import uuid

from celery import Task

from app.core.logging import get_logger
from app.domains.transcriptions.models import JobStatus
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


def get_sync_db():
    """Synchronous DB session for use inside Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings

    engine = create_engine(settings.database_url_sync)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def update_job_status_sync(db, job_id: uuid.UUID, status: JobStatus, error: str | None = None):
    from app.domains.transcriptions.models import TranscriptionJob
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if job:
        job.status = status
        if error:
            job.error_message = error
        db.commit()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="transcriptions.transcribe",
)
def transcribe_audio(self: Task, job_id: str, file_path: str, language: str | None, model_size: str) -> dict:
    db = get_sync_db()
    job_uuid = uuid.UUID(job_id)

    try:
        logger.info("transcription_started", job_id=job_id, model=model_size)
        update_job_status_sync(db, job_uuid, JobStatus.PROCESSING)

        from faster_whisper import WhisperModel
        from app.core.config import settings

        model = WhisperModel(
            model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

        start_time = time.time()
        segments, info = model.transcribe(file_path, language=language)

        full_text = " ".join(segment.text.strip() for segment in segments)
        processing_time = time.time() - start_time

        # Save transcript
        from app.domains.transcriptions.models import Transcript, TranscriptionJob
        job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_uuid).first()

        transcript = Transcript(
            job_id=job_uuid,
            full_text=full_text,
            language_detected=info.language,
            duration_seconds=info.duration,
            processing_time_seconds=processing_time,
            word_count=len(full_text.split()),
        )
        db.add(transcript)

        job.status = JobStatus.COMPLETED
        db.commit()

        logger.info(
            "transcription_completed",
            job_id=job_id,
            duration=info.duration,
            processing_time=processing_time,
        )

        return {"job_id": job_id, "status": "completed"}

    except Exception as exc:
        logger.error("transcription_failed", job_id=job_id, error=str(exc))
        update_job_status_sync(db, job_uuid, JobStatus.FAILED, error_message=str(exc))

        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("transcription_max_retries_exceeded", job_id=job_id)
            return {"job_id": job_id, "status": "failed"}
    finally:
        db.close()