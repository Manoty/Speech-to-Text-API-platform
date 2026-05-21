import pytest
from httpx import AsyncClient


async def get_token(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "pass12345"})
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "pass12345"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_search_no_results(client: AsyncClient):
    token = await get_token(client, "search@example.com")
    resp = await client.get(
        "/api/v1/transcriptions/search?q=zzznomatch",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["query"] == "zzznomatch"


@pytest.mark.asyncio
async def test_search_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/transcriptions/search?q=hello")
    assert resp.status_code == 403