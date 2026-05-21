"""
app/api/v1/apikeys.py
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.domains.auth.models import User
from app.domains.apikeys.schemas import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse
from app.domains.apikeys.service import ApiKeyService

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("/", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreatedResponse:
    service = ApiKeyService(db)
    return await service.create_key(user_id=current_user.id, name=payload.name)


@router.get("/", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyResponse]:
    service = ApiKeyService(db)
    return await service.list_keys(user_id=current_user.id)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = ApiKeyService(db)
    await service.revoke_key(key_id=key_id, user_id=current_user.id)