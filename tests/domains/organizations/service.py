"""
app/domains/organizations/service.py
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.domains.auth.repository import UserRepository
from app.domains.organizations.models import OrgRole
from app.domains.organizations.repository import OrganizationRepository
from app.domains.organizations.schemas import (
    OrganizationDetailResponse,
    OrganizationResponse,
    MemberResponse,
)


class OrganizationService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = OrganizationRepository(db)
        self.user_repo = UserRepository(db)

    async def create(
        self, name: str, slug: str, creator_id: uuid.UUID
    ) -> OrganizationResponse:
        existing = await self.repo.get_by_slug(slug)
        if existing:
            raise ConflictError(f"Slug '{slug}' is already taken")

        org = await self.repo.create(name=name, slug=slug)

        # Creator becomes owner automatically
        await self.repo.add_member(
            org_id=org.id,
            user_id=creator_id,
            role=OrgRole.OWNER,
        )

        return OrganizationResponse.model_validate(org)

    async def get_detail(
        self, org_id: uuid.UUID, requesting_user_id: uuid.UUID
    ) -> OrganizationDetailResponse:
        org = await self.repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("Organization")

        # Only members can view org details
        member = await self.repo.get_member(org_id, requesting_user_id)
        if not member:
            raise PermissionDeniedError("Not a member of this organization")

        members = await self.repo.list_members(org_id)

        return OrganizationDetailResponse(
            organization=OrganizationResponse.model_validate(org),
            members=[MemberResponse.model_validate(m) for m in members],
            total_members=len(members),
        )

    async def invite_member(
        self,
        org_id: uuid.UUID,
        email: str,
        role: OrgRole,
        inviting_user_id: uuid.UUID,
    ) -> MemberResponse:
        # Only owner/admin can invite
        inviter = await self.repo.get_member(org_id, inviting_user_id)
        if not inviter or inviter.role not in (OrgRole.OWNER, OrgRole.ADMIN):
            raise PermissionDeniedError("Only org admins can invite members")

        target_user = await self.user_repo.get_by_email(email)
        if not target_user:
            raise NotFoundError("User with that email")

        existing = await self.repo.get_member(org_id, target_user.id)
        if existing:
            raise ConflictError("User is already a member")

        member = await self.repo.add_member(
            org_id=org_id,
            user_id=target_user.id,
            role=role,
        )
        return MemberResponse.model_validate(member)

    async def remove_member(
        self,
        org_id: uuid.UUID,
        target_user_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
    ) -> None:
        requester = await self.repo.get_member(org_id, requesting_user_id)
        if not requester or requester.role not in (OrgRole.OWNER, OrgRole.ADMIN):
            raise PermissionDeniedError("Only org admins can remove members")

        target = await self.repo.get_member(org_id, target_user_id)
        if not target:
            raise NotFoundError("Member")

        await self.repo.remove_member(target)