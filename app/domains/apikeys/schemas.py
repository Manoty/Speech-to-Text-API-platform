"""
app/domains/apikeys/schemas.py
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ApiKeyCreatedResponse(BaseModel):
    """
    Returned ONCE on creation only.
    raw_key is never stored — user must save it immediately.
    """
    id: uuid.UUID
    name: str
    key_prefix: str
    raw_key: str
    created_at: datetime


class ApiKeyResponse(BaseModel):
    """Safe response — no raw key, no hash."""
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime