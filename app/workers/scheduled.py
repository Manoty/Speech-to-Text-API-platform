"""
app/workers/scheduled.py

Celery Beat scheduled tasks.

reset_monthly_quotas  — runs 1st of each month, resets all users
cleanup_orphaned_files — runs daily, deletes uploaded files with no job
"""

import os
from datetime import date, timedelta
from pathlib import Path

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


def get_sync_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    engine = create_engine(settings.database_url_sync)
    return sessionmaker(bind=engine)()


def _next_reset_date() -> date:
    today = date.today()
    if today.month == 12:
        return date(today.year + 1, 1, 1)
    return date(today.year, today.month + 1, 1)


@celery_app.task(name="scheduled.reset_monthly_quotas")
def reset_monthly_quotas() -> dict:
    db = get_sync_db()
    try:
        from app.domains.quotas.models import UserQuota
        quotas = db.query(UserQuota).all()
        new_reset = _next_reset_date()
        for quota in quotas:
            quota.minutes_used_this_month = 0.0
            quota.reset_date = new_reset
        db.commit()
        logger.info("quotas_reset", count=len(quotas), next_reset=str(new_reset))
        return {"reset_count": len(quotas)}
    except Exception as exc:
        logger.error("quota_reset_failed", error=str(exc))
        db.rollback()
        return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="scheduled.cleanup_orphaned_files")
def cleanup_orphaned_files() -> dict:
    """
    Delete UploadedFile records and disk files older than 24h
    that have no associated TranscriptionJob.
    This catches files where the job creation failed mid-way.
    """
    db = get_sync_db()
    try:
        from sqlalchemy import text
        from app.core.config import settings

        result = db.execute(text("""
            SELECT uf.id, uf.file_path
            FROM uploaded_files uf
            LEFT JOIN transcription_jobs tj ON tj.file_id = uf.id
            WHERE tj.id IS NULL
              AND uf.created_at < NOW() - INTERVAL '24 hours'
        """))
        rows = result.fetchall()

        deleted_files = 0
        deleted_db = 0

        for row in rows:
            file_path = row[1]
            # Delete from disk
            path = Path(file_path)
            if path.exists():
                path.unlink()
                deleted_files += 1

            # Delete DB record
            db.execute(
                text("DELETE FROM uploaded_files WHERE id = :id"),
                {"id": row[0]},
            )
            deleted_db += 1

        db.commit()
        logger.info(
            "orphan_cleanup_complete",
            deleted_db=deleted_db,
            deleted_files=deleted_files,
        )
        return {"deleted_db": deleted_db, "deleted_files": deleted_files}
    except Exception as exc:
        logger.error("orphan_cleanup_failed", error=str(exc))
        db.rollback()
        return {"error": str(exc)}
    finally:
        db.close()