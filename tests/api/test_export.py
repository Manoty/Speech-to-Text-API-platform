import io
import pytest
from unittest.mock import patch
from httpx import AsyncClient


async def get_token(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "pass12345"})
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "pass12345"})
    return r.json()["access_token"]


async def create_completed_job(client: AsyncClient, token: str, db) -> str:
    """Upload a file and manually mark it completed for export testing."""
    with patch("app.domains.transcriptions.service.transcribe_audio") as mock:
        mock.delay.return_value.id = "fake-task-id"
        resp = await client.post(
            "/api/v1/transcriptions/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.mp3", io.BytesIO(b"fake audio"), "audio/mpeg")},
        )
    job_id = resp.json()["id"]

    from app.domains.transcriptions.models import JobStatus, Transcript, TranscriptionJob
    from sqlalchemy import select

    result = await db.execute(select(TranscriptionJob).where(TranscriptionJob.id == job_id))
    job = result.scalar_one()
    job.status = JobStatus.COMPLETED

    transcript = Transcript(
        job_id=job.id,
        full_text="Hello world this is a test transcription.",
        language_detected="en",
        duration_seconds=10.0,
        processing_time_seconds=2.0,
        word_count=8,
        segments=[
            {"start": 0.0, "end": 1.0, "word": "Hello", "probability": 0.99},
            {"start": 1.0, "end": 1.5, "word": "world", "probability": 0.98},
            {"start": 1.5, "end": 2.0, "word": "this", "probability": 0.97},
            {"start": 2.0, "end": 2.3, "word": "is", "probability": 0.99},
            {"start": 2.3, "end": 2.5, "word": "a", "probability": 0.99},
            {"start": 2.5, "end": 2.9, "word": "test", "probability": 0.98},
        ],
    )
    db.add(transcript)
    await db.flush()
    return str(job_id)


@pytest.mark.asyncio
async def test_export_srt(client: AsyncClient, db):
    token = await get_token(client, "exportsrt@example.com")
    job_id = await create_completed_job(client, token, db)

    resp = await client.get(
        f"/api/v1/transcriptions/{job_id}/export?format=srt",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "Content-Disposition" in resp.headers
    assert ".srt" in resp.headers["Content-Disposition"]
    content = resp.text
    assert "-->" in content
    assert "Hello" in content


@pytest.mark.asyncio
async def test_export_vtt(client: AsyncClient, db):
    token = await get_token(client, "exportvtt@example.com")
    job_id = await create_completed_job(client, token, db)

    resp = await client.get(
        f"/api/v1/transcriptions/{job_id}/export?format=vtt",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.text.startswith("WEBVTT")


@pytest.mark.asyncio
async def test_export_txt(client: AsyncClient, db):
    token = await get_token(client, "exporttxt@example.com")
    job_id = await create_completed_job(client, token, db)

    resp = await client.get(
        f"/api/v1/transcriptions/{job_id}/export?format=txt",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "Hello world" in resp.text