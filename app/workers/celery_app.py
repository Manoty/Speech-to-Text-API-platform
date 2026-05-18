"""
app/workers/celery_app.py

Celery application factory.
Tasks are auto-discovered from domains/*/tasks.py
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "stt_platform",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.domains.transcriptions.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,              # only ack after task completes (safer)
    worker_prefetch_multiplier=1,     # one task at a time per worker (transcription is heavy)
    result_expires=3600,              # results expire after 1 hour
)