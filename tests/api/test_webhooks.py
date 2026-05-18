import pytest
from httpx import AsyncClient


async def auth_token(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "pass12345"})
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "pass12345"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_create_webhook(client: AsyncClient):
    token = await auth_token(client, "hook@example.com")
    resp = await client.post(
        "/api/v1/webhooks/",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://example.com/hook", "description": "My hook"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["url"] == "https://example.com/hook"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_webhooks(client: AsyncClient):
    token = await auth_token(client, "listwhook@example.com")
    await client.post(
        "/api/v1/webhooks/",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://example.com/hook1"},
    )
    resp = await client.get(
        "/api/v1/webhooks/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_webhook(client: AsyncClient):
    token = await auth_token(client, "delwhook@example.com")
    create = await client.post(
        "/api/v1/webhooks/",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://example.com/hook"},
    )
    endpoint_id = create.json()["id"]
    resp = await client.delete(
        f"/api/v1/webhooks/{endpoint_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204