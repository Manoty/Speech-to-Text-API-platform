"""
app/domains/transcriptions/tasks.py — updated for Phase 3
"""

import json
import time
import uuid

from celery import Task

from app.core.logging import get_logger
from app.domains.transcriptions.models import JobStatus
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


def get_sync_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    engine = create_engine(settings.database_url_sync)
    return sessionmaker(bind=engine)()


def publish_job_update(job_id: str, status: str, user_id: str) -> None:
    """Publish to Redis pub/sub so WebSocket handlers can push to clients."""
    import redis
    from app.core.config import settings
    r = redis.from_url(settings.redis_url)
    channel = f"job_updates:{user_id}"
    message = json.dumps({"job_id": job_id, "status": status})
    r.publish(channel, message)


def fire_webhooks(db, job_id: uuid.UUID, user_id: uuid.UUID, status: str) -> None:
    """Enqueue a webhook delivery task for each active endpoint."""
    from app.domains.webhooks.models import WebhookEndpoint
    from app.domains.webhooks.tasks import deliver_webhook

    endpoints = (
        db.query(WebhookEndpoint)
        .filter(
            WebhookEndpoint.user_id == user_id,
            WebhookEndpoint.is_active == True,
        )
        .all()
    )

    payload = {
        "event": "transcription.completed",
        "job_id": str(job_id),
        "status": status,
    }

    for ep in endpoints:
        deliver_webhook.delay(
            endpoint_id=str(ep.id),
            endpoint_url=ep.url,
            secret=ep.secret,
            job_id=str(job_id),
            payload=payload,
        )


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="transcriptions.transcribe",
)
def transcribe_audio(
    self: Task,
    job_id: str,
    file_path: str,
    language: str | None,
    model_size: str,
    user_id: str,
) -> dict:
    db = get_sync_db()
    job_uuid = uuid.UUID(job_id)
    user_uuid = uuid.UUID(user_id)

    try:
        logger.info("transcription_started", job_id=job_id, model=model_size)

        from app.domains.transcriptions.models import TranscriptionJob
        job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_uuid).first()
        job.status = JobStatus.PROCESSING
        db.commit()

        publish_job_update(job_id, "processing", user_id)

        # If S3, download first
        actual_path = file_path
        if file_path.startswith("uploads/"):
            import tempfile, boto3
            from app.core.config import settings
            client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
            )
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".audio")
            client.download_fileobj(settings.s3_bucket, file_path, tmp)
            actual_path = tmp.name

        from faster_whisper import WhisperModel
        from app.core.config import settings

        model = WhisperModel(
            model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

        start_time = time.time()
        segments, info = model.transcribe(actual_path, language=language)
        full_text = " ".join(seg.text.strip() for seg in segments)
        processing_time = time.time() - start_time

        from app.domains.transcriptions.models import Transcript
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

        publish_job_update(job_id, "completed", user_id)
        fire_webhooks(db, job_uuid, user_uuid, "completed")

        logger.info(
            "transcription_completed",
            job_id=job_id,
            language=info.language,
            duration=info.duration,
            processing_time=processing_time,
        )
        return {"job_id": job_id, "status": "completed"}

    except Exception as exc:
        logger.error("transcription_failed", job_id=job_id, error=str(exc))

        from app.domains.transcriptions.models import TranscriptionJob
        job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_uuid).first()
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            db.commit()

        publish_job_update(job_id, "failed", user_id)
        fire_webhooks(db, job_uuid, user_uuid, "failed")

        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"job_id": job_id, "status": "failed"}
    finally:
        db.close()