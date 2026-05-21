"""
tests/performance/test_query_performance.py

Verifies critical queries stay under latency thresholds.
Uses EXPLAIN ANALYZE via SQLAlchemy to catch missing indexes early.

Run with: pytest tests/performance/ -v -m performance
"""

import time
import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


async def seed_jobs(db, user_id: uuid.UUID, count: int = 100) -> None:
    from app.domains.auth.models import User
    from app.domains.transcriptions.models import (
        JobStatus, TranscriptionJob, UploadedFile,
    )

    for i in range(count):
        f = UploadedFile(
            user_id=user_id,
            original_filename=f"test_{i}.mp3",
            stored_filename=f"{uuid.uuid4()}.mp3",
            file_path=f"./uploads/{uuid.uuid4()}.mp3",
            file_size=1024 * 1024,
            mime_type="audio/mpeg",
        )
        db.add(f)
        await db.flush()

        job = TranscriptionJob(
            user_id=user_id,
            file_id=f.id,
            model_size="base",
            status=JobStatus.COMPLETED,
        )
        db.add(job)

    await db.flush()


@pytest.mark.asyncio
async def test_list_jobs_query_performance(db):
    from app.domains.auth.models import User
    user = User(email="perf@test.com", hashed_password="x", is_active=True)
    db.add(user)
    await db.flush()

    await seed_jobs(db, user.id, count=500)

    start = time.perf_counter()
    from app.domains.transcriptions.repository import TranscriptionRepository
    repo = TranscriptionRepository(db)
    jobs, total = await repo.list_jobs(user_id=user.id, page=1, page_size=20)
    duration = time.perf_counter() - start

    assert len(jobs) == 20
    assert total == 500
    assert duration < 0.2, f"list_jobs too slow: {duration:.3f}s (threshold: 0.2s)"


@pytest.mark.asyncio
async def test_job_by_id_query_performance(db):
    from app.domains.auth.models import User
    user = User(email="perf2@test.com", hashed_password="x", is_active=True)
    db.add(user)
    await db.flush()

    await seed_jobs(db, user.id, count=100)

    from app.domains.transcriptions.models import TranscriptionJob
    from sqlalchemy import select
    result = await db.execute(
        select(TranscriptionJob).where(TranscriptionJob.user_id == user.id).limit(1)
    )
    job = result.scalar_one()

    start = time.perf_counter()
    from app.domains.transcriptions.repository import TranscriptionRepository
    repo = TranscriptionRepository(db)
    fetched = await repo.get_job_by_id(job.id, user.id)
    duration = time.perf_counter() - start

    assert fetched is not None
    assert duration < 0.05, f"get_job_by_id too slow: {duration:.3f}s (threshold: 0.05s)"


@pytest.mark.asyncio
async def test_explain_analyze_list_jobs(db):
    """
    Run EXPLAIN ANALYZE and assert no sequential scans on large tables.
    Catches missing indexes before they hit production.
    """
    plan = await db.execute(text("""
        EXPLAIN ANALYZE
        SELECT * FROM transcription_jobs
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        LIMIT 20
    """).bindparams(user_id=uuid.uuid4()))

    rows = [row[0] for row in plan.fetchall()]
    plan_text = "\n".join(rows)

    # Should use index scan, not sequential scan
    assert "Seq Scan on transcription_jobs" not in plan_text, (
        f"Missing index detected!\n{plan_text}"
    )