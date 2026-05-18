"""
app/api/v1/webhooks.py
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.domains.auth.models import User
from app.domains.webhooks.schemas import WebhookEndpointCreate, WebhookEndpointResponse
from app.domains.webhooks.service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/", response_model=WebhookEndpointResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    payload: WebhookEndpointCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookEndpointResponse:
    service = WebhookService(db)
    return await service.create_endpoint(
        user_id=current_user.id,
        url=str(payload.url),
        secret=payload.secret,
        description=payload.description,
    )


@router.get("/", response_model=list[WebhookEndpointResponse])
async def list_webhooks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookEndpointResponse]:
    service = WebhookService(db)
    return await service.list_endpoints(user_id=current_user.id)


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    endpoint_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = WebhookService(db)
    await service.delete_endpoint(endpoint_id=endpoint_id, user_id=current_user.id)