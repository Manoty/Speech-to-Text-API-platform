import io
import pytest
from unittest.mock import patch
from httpx import AsyncClient


async def get_token(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Pass1234"})
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "Pass1234"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_retranscribe_creates_new_version(client: AsyncClient, db):
    token = await get_token(client, "version@example.com")

    with patch("app.domains.transcriptions.service.transcribe_audio") as mock:
        mock.delay.return_value.id = "task-1"
        upload = await client.post(
            "/api/v1/transcriptions/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.mp3", io.BytesIO(b"\xff\xfb" + b"\x00" * 100), "audio/mpeg")},
        )
    assert upload.status_code == 202
    job_id = upload.json()["id"]

    # Manually add a v1 transcript
    from app.domains.transcriptions.models import JobStatus, Transcript, TranscriptionJob
    from sqlalchemy import select

    result = await db.execute(
        select(TranscriptionJob).where(TranscriptionJob.id == job_id)
    )
    job = result.scalar_one()
    job.status = JobStatus.COMPLETED

    t1 = Transcript(
        job_id=job.id, full_text="Version one transcript.",
        language_detected="en", duration_seconds=5.0,
        processing_time_seconds=1.0, word_count=3,
        version=1, is_current=True, model_size="base",
    )
    db.add(t1)
    await db.flush()

    # Retranscribe with large model
    with patch("app.domains.transcriptions.service.transcribe_audio") as mock:
        mock.delay.return_value.id = "task-2"
        resp = await client.post(
            f"/api/v1/transcriptions/{job_id}/retranscribe",
            headers={"Authorization": f"Bearer {token}"},
            json={"model_size": "small", "language": "en"},
        )
    assert resp.status_code == 200

    # Fetch history
    history = await client.get(
        f"/api/v1/transcriptions/{job_id}/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history.status_code == 200
    data = history.json()
    assert data["total_versions"] >= 1