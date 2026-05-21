import pytest
from httpx import AsyncClient


async def get_token(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Pass1234"})
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "Pass1234"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_create_organization(client: AsyncClient):
    token = await get_token(client, "orgowner@example.com")
    resp = await client.post(
        "/api/v1/organizations/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Acme Corp", "slug": "acme-corp"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "acme-corp"
    assert data["name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_duplicate_slug_rejected(client: AsyncClient):
    token = await get_token(client, "dupslug@example.com")
    payload = {"name": "Test Org", "slug": "test-org-dup"}
    await client.post(
        "/api/v1/organizations/",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    resp = await client.post(
        "/api/v1/organizations/",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_organization_detail(client: AsyncClient):
    token = await get_token(client, "orgdetail@example.com")
    create = await client.post(
        "/api/v1/organizations/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Detail Org", "slug": "detail-org"},
    )
    org_id = create.json()["id"]
    resp = await client.get(
        f"/api/v1/organizations/{org_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total_members"] == 1


@pytest.mark.asyncio
async def test_non_member_cannot_view_org(client: AsyncClient):
    owner_token = await get_token(client, "orgowner2@example.com")
    outsider_token = await get_token(client, "outsider@example.com")

    create = await client.post(
        "/api/v1/organizations/",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Private Org", "slug": "private-org"},
    )
    org_id = create.json()["id"]

    resp = await client.get(
        f"/api/v1/organizations/{org_id}",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert resp.status_code == 403