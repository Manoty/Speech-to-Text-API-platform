"""
app/domains/organizations/schemas.py
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.organizations.models import OrgRole


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9\-]+$")


class OrganizationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime


class MemberResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    role: OrgRole
    is_active: bool
    created_at: datetime


class InviteMemberRequest(BaseModel):
    email: str
    role: OrgRole = OrgRole.MEMBER


class OrganizationDetailResponse(BaseModel):
    organization: OrganizationResponse
    members: list[MemberResponse]
    total_members: int