import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def make_admin_token(client: AsyncClient, db: AsyncSession) -> str:
    await client.post("/api/v1/auth/register", json={
        "email": "costadmin@example.com", "password": "Pass1234"
    })
    from app.domains.auth.models import User
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.email == "costadmin@example.com")
    )
    user = result.scalar_one()
    user.is_admin = True
    await db.flush()

    r = await client.post("/api/v1/auth/login", json={
        "email": "costadmin@example.com", "password": "Pass1234"
    })
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_cost_dashboard_admin(client: AsyncClient, db: AsyncSession):
    token = await make_admin_token(client, db)
    resp = await client.get(
        "/api/v1/admin/costs/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_cost_usd" in data
    assert "by_model" in data
    assert "top_users" in data
    assert "monthly_trend" in data


@pytest.mark.asyncio
async def test_cost_dashboard_non_admin(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "costuser@example.com", "password": "Pass1234"
    })
    r = await client.post("/api/v1/auth/login", json={
        "email": "costuser@example.com", "password": "Pass1234"
    })
    token = r.json()["access_token"]
    resp = await client.get(
        "/api/v1/admin/costs/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403