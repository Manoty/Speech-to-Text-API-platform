"""
app/api/v1/organizations.py
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.domains.auth.models import User
from app.domains.organizations.schemas import (
    InviteMemberRequest,
    MemberResponse,
    OrganizationCreate,
    OrganizationDetailResponse,
    OrganizationResponse,
)
from app.domains.organizations.service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    service = OrganizationService(db)
    return await service.create(
        name=payload.name,
        slug=payload.slug,
        creator_id=current_user.id,
    )


@router.get("/{org_id}", response_model=OrganizationDetailResponse)
async def get_organization(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationDetailResponse:
    service = OrganizationService(db)
    return await service.get_detail(
        org_id=org_id,
        requesting_user_id=current_user.id,
    )


@router.post("/{org_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    org_id: uuid.UUID,
    payload: InviteMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    service = OrganizationService(db)
    return await service.invite_member(
        org_id=org_id,
        email=payload.email,
        role=payload.role,
        inviting_user_id=current_user.id,
    )


@router.delete("/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = OrganizationService(db)
    await service.remove_member(
        org_id=org_id,
        target_user_id=user_id,
        requesting_user_id=current_user.id,
    )