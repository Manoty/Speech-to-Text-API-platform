import io
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


async def get_auth_token(client: AsyncClient, email: str = "trans@example.com") -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "pass12345"})
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "pass12345"})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_upload_audio(client: AsyncClient):
    token = await get_auth_token(client)

    # Patch Celery task so it doesn't actually run
    with patch("app.domains.transcriptions.service.transcribe_audio") as mock_task:
        mock_task.delay.return_value.id = "fake-celery-id"

        fake_audio = io.BytesIO(b"fake audio content")
        resp = await client.post(
            "/api/v1/transcriptions/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.mp3", fake_audio, "audio/mpeg")},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_jobs_empty(client: AsyncClient):
    token = await get_auth_token(client, "list@example.com")
    resp = await client.get(
        "/api/v1/transcriptions/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_job_not_found(client: AsyncClient):
    token = await get_auth_token(client, "notfound@example.com")
    resp = await client.get(
        "/api/v1/transcriptions/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404