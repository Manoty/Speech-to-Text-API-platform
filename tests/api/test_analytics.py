import pytest
from httpx import AsyncClient


async def make_admin(client: AsyncClient, db) -> str:
    """Register a user then flip is_admin directly in DB."""
    from app.domains.auth.models import User
    from sqlalchemy import select

    await client.post("/api/v1/auth/register", json={
        "email": "admin@example.com", "password": "adminpass123"
    })
    result = await db.execute(select(User).where(User.email == "admin@example.com"))
    user = result.scalar_one()
    user.is_admin = True
    await db.flush()

    r = await client.post("/api/v1/auth/login", json={
        "email": "admin@example.com", "password": "adminpass123"
    })
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_platform_stats_admin(client: AsyncClient, db):
    token = await make_admin(client, db)
    resp = await client.get(
        "/api/v1/admin/analytics/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "total_jobs" in data


@pytest.mark.asyncio
async def test_platform_stats_non_admin(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "nonadmin@example.com", "password": "pass12345"
    })
    r = await client.post("/api/v1/auth/login", json={
        "email": "nonadmin@example.com", "password": "pass12345"
    })
    token = r.json()["access_token"]
    resp = await client.get(
        "/api/v1/admin/analytics/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403