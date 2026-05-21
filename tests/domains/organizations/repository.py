"""
app/domains/organizations/repository.py
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.organizations.models import OrgRole, Organization, OrganizationMember


class OrganizationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, name: str, slug: str) -> Organization:
        org = Organization(name=name, slug=slug)
        self.db.add(org)
        await self.db.flush()
        return org

    async def get_by_id(self, org_id: uuid.UUID) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none()

    async def add_member(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        role: OrgRole,
    ) -> OrganizationMember:
        member = OrganizationMember(
            organization_id=org_id,
            user_id=user_id,
            role=role,
        )
        self.db.add(member)
        await self.db.flush()
        return member

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def list_members(self, org_id: uuid.UUID) -> list[OrganizationMember]:
        result = await self.db.execute(
            select(OrganizationMember)
            .where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.is_active == True,
            )
            .options(selectinload(OrganizationMember.user))
            .order_by(OrganizationMember.created_at.asc())
        )
        return list(result.scalars().all())

    async def remove_member(self, member: OrganizationMember) -> None:
        member.is_active = False
        await self.db.flush()

    async def get_user_org(self, user_id: uuid.UUID) -> Organization | None:
        result = await self.db.execute(
            select(Organization)
            .join(
                OrganizationMember,
                OrganizationMember.organization_id == Organization.id,
            )
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active == True,
                Organization.is_active == True,
            )
        )
        return result.scalar_one_or_none()