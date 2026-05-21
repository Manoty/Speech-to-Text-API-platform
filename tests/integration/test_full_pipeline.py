"""
tests/integration/test_full_pipeline.py

End-to-end pipeline test.
Uses a real tiny audio file and actual faster-whisper transcription.
Marked as integration — skipped in normal pytest runs.
Run with: pytest tests/integration/ -v -m integration

WHY separate from unit tests?
Integration tests are slow (real transcription = seconds).
They should run in CI on merge to main, not on every commit.
"""

import io
import time

import pytest

# Skip unless explicitly running integration tests
pytestmark = pytest.mark.skipif(
    "not config.getoption('--integration')",
    reason="Integration tests not requested",
)


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests",
    )


@pytest.mark.asyncio
async def test_full_transcription_pipeline(client):
    """
    Full pipeline:
    register → login → upload real audio → worker transcribes
    → poll until completed → fetch transcript → export SRT
    """
    # 1. Register + login
    await client.post("/api/v1/auth/register", json={
        "email": "pipeline@test.com",
        "password": "testpass123",
    })
    login = await client.post("/api/v1/auth/login", json={
        "email": "pipeline@test.com",
        "password": "testpass123",
    })
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload a tiny real audio file (sine wave WAV — 1 second)
    # Generate a minimal WAV header + silence
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00" * 16000 * 2)  # 1 second of silence
    buf.seek(0)

    upload = await client.post(
        "/api/v1/transcriptions/upload",
        headers=headers,
        files={"file": ("test.wav", buf, "audio/wav")},
    )
    assert upload.status_code == 202
    job_id = upload.json()["id"]
    assert upload.json()["status"] == "pending"

    # 3. Poll until completed or timeout (30s)
    deadline = time.time() + 30
    status = "pending"
    while time.time() < deadline and status not in ("completed", "failed"):
        time.sleep(2)
        poll = await client.get(
            f"/api/v1/transcriptions/{job_id}",
            headers=headers,
        )
        assert poll.status_code == 200
        status = poll.json()["job"]["status"]

    assert status == "completed", f"Job did not complete in time, status={status}"

    # 4. Fetch full detail
    detail = await client.get(
        f"/api/v1/transcriptions/{job_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    data = detail.json()
    assert data["transcript"] is not None
    assert isinstance(data["transcript"]["word_count"], int)

    # 5. Export SRT
    export = await client.get(
        f"/api/v1/transcriptions/{job_id}/export?format=srt",
        headers=headers,
    )
    assert export.status_code == 200
    assert "-->" in export.text

    # 6. Export VTT
    export_vtt = await client.get(
        f"/api/v1/transcriptions/{job_id}/export?format=vtt",
        headers=headers,
    )
    assert export_vtt.status_code == 200
    assert export_vtt.text.startswith("WEBVTT")