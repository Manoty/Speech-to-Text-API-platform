import pytest
from httpx import AsyncClient


async def get_token(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "pass12345"})
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "pass12345"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient):
    token = await get_token(client, "apikey@example.com")
    resp = await client.post(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "My Server Key"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Server Key"
    assert "raw_key" in data
    assert data["raw_key"].startswith("stt_")
    assert "key_prefix" in data


@pytest.mark.asyncio
async def test_list_api_keys(client: AsyncClient):
    token = await get_token(client, "listkeys@example.com")
    await client.post(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Key One"},
    )
    resp = await client.get(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert "raw_key" not in resp.json()[0]


@pytest.mark.asyncio
async def test_revoke_api_key(client: AsyncClient):
    token = await get_token(client, "revokekey@example.com")
    create = await client.post(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Temp Key"},
    )
    key_id = create.json()["id"]
    resp = await client.delete(
        f"/api/v1/api-keys/{key_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_auth_with_api_key(client: AsyncClient):
    token = await get_token(client, "apikeyauth@example.com")
    create = await client.post(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Auth Test Key"},
    )
    raw_key = create.json()["raw_key"]

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": raw_key},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "apikeyauth@example.com"