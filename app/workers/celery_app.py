"""
app/workers/celery_app.py — updated for Phase 4
Adds: Celery Beat schedule
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "stt_platform",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.domains.transcriptions.tasks",
        "app.domains.webhooks.tasks",
        "app.workers.scheduled",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    beat_schedule={
        # Reset all user quotas on the 1st of every month at midnight UTC
        "reset-monthly-quotas": {
            "task": "scheduled.reset_monthly_quotas",
            "schedule": crontab(day_of_month="1", hour="0", minute="0"),
        },
        # Clean up orphaned upload files daily at 2am UTC
        "cleanup-orphaned-files": {
            "task": "scheduled.cleanup_orphaned_files",
            "schedule": crontab(hour="2", minute="0"),
        },
    },
)