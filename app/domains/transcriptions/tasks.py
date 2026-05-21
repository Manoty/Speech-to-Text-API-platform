"""
app/domains/transcriptions/tasks.py — updated for Phase 4
Adds: word timestamps, quota recording, email notifications
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
    import redis
    from app.core.config import settings
    r = redis.from_url(settings.redis_url)
    channel = f"job_updates:{user_id}"
    message = json.dumps({"job_id": job_id, "status": status})
    r.publish(channel, message)


def fire_webhooks(db, job_id: uuid.UUID, user_id: uuid.UUID, status: str) -> None:
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


def send_completion_email(
    user_email: str,
    full_name: str | None,
    job_id: str,
    duration_seconds: float | None,
    word_count: int,
) -> None:
    from app.core.email import render_transcription_complete, send_email_sync
    subject, html = render_transcription_complete(
        full_name=full_name,
        job_id=job_id,
        duration_seconds=duration_seconds,
        word_count=word_count,
    )
    send_email_sync(user_email, subject, html)


def send_failure_email(
    user_email: str,
    full_name: str | None,
    job_id: str,
    error_message: str | None,
) -> None:
    from app.core.email import render_transcription_failed, send_email_sync
    subject, html = render_transcription_failed(
        full_name=full_name,
        job_id=job_id,
        error_message=error_message,
    )
    send_email_sync(user_email, subject, html)


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
        job = db.query(TranscriptionJob).filter(
            TranscriptionJob.id == job_uuid
        ).first()
        job.status = JobStatus.PROCESSING
        db.commit()

        publish_job_update(job_id, "processing", user_id)

        # Download from S3 if needed
        actual_path = file_path
        if not file_path.startswith("/") and not file_path.startswith("./"):
            import tempfile
            import boto3
            from app.core.config import settings as cfg
            client = boto3.client(
                "s3",
                endpoint_url=cfg.s3_endpoint_url,
                aws_access_key_id=cfg.s3_access_key,
                aws_secret_access_key=cfg.s3_secret_key,
            )
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".audio")
            client.download_fileobj(cfg.s3_bucket, file_path, tmp)
            tmp.close()
            actual_path = tmp.name

        from faster_whisper import WhisperModel
        from app.core.config import settings

        model = WhisperModel(
            model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

        start_time = time.time()
        segments_raw, info = model.transcribe(
            actual_path,
            language=language,
            word_timestamps=settings.whisper_word_timestamps,
        )

        # Collect segments and word timestamps
        all_words = []
        text_parts = []

        for segment in segments_raw:
            text_parts.append(segment.text.strip())
            if settings.whisper_word_timestamps and segment.words:
                for word in segment.words:
                    all_words.append({
                        "start": round(word.start, 3),
                        "end": round(word.end, 3),
                        "word": word.word,
                        "probability": round(word.probability, 3),
                    })

        full_text = " ".join(text_parts)
        processing_time = time.time() - start_time

        from app.domains.transcriptions.models import Transcript
        transcript = Transcript(
            job_id=job_uuid,
            full_text=full_text,
            language_detected=info.language,
            duration_seconds=info.duration,
            processing_time_seconds=processing_time,
            word_count=len(full_text.split()),
            segments=all_words if all_words else None,
        )
        db.add(transcript)

        # Update search vector
        job.status = JobStatus.COMPLETED
        db.commit()

        # Update search vector via raw SQL
        db.execute(
            __import__("sqlalchemy").text(
                "UPDATE transcripts SET search_vector = to_tsvector('english', full_text) "
                "WHERE id = :id"
            ),
            {"id": transcript.id},
        )
        db.commit()

        # Record quota usage
        from app.domains.quotas.models import UserQuota
        quota = db.query(UserQuota).filter(UserQuota.user_id == user_uuid).first()
        if quota and info.duration:
            quota.minutes_used_this_month += info.duration / 60
            db.commit()

        # Get user for email
        from app.domains.auth.models import User
        user = db.query(User).filter(User.id == user_uuid).first()

        publish_job_update(job_id, "completed", user_id)
        fire_webhooks(db, job_uuid, user_uuid, "completed")

        if user:
            send_completion_email(
                user_email=user.email,
                full_name=user.full_name,
                job_id=job_id,
                duration_seconds=info.duration,
                word_count=transcript.word_count,
            )

        logger.info(
            "transcription_completed",
            job_id=job_id,
            language=info.language,
            duration=info.duration,
            processing_time=processing_time,
            words=len(all_words),
        )
        return {"job_id": job_id, "status": "completed"}

    except Exception as exc:
        logger.error("transcription_failed", job_id=job_id, error=str(exc))

        from app.domains.transcriptions.models import TranscriptionJob
        job = db.query(TranscriptionJob).filter(
            TranscriptionJob.id == job_uuid
        ).first()
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            db.commit()

        from app.domains.auth.models import User
        user = db.query(User).filter(User.id == user_uuid).first()

        publish_job_update(job_id, "failed", user_id)
        fire_webhooks(db, job_uuid, user_uuid, "failed")

        if user:
            send_failure_email(
                user_email=user.email,
                full_name=user.full_name,
                job_id=job_id,
                error_message=str(exc),
            )

        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"job_id": job_id, "status": "failed"}
    finally:
        db.close()