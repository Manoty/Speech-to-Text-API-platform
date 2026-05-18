"""
app/domains/webhooks/service.py
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.webhooks.repository import WebhookRepository
from app.domains.webhooks.schemas import WebhookEndpointResponse


class WebhookService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = WebhookRepository(db)

    async def create_endpoint(
        self,
        user_id: uuid.UUID,
        url: str,
        secret: str | None,
        description: str | None,
    ) -> WebhookEndpointResponse:
        endpoint = await self.repo.create_endpoint(
            user_id=user_id, url=url, secret=secret, description=description
        )
        return WebhookEndpointResponse.model_validate(endpoint)

    async def list_endpoints(self, user_id: uuid.UUID) -> list[WebhookEndpointResponse]:
        endpoints = await self.repo.list_endpoints(user_id)
        return [WebhookEndpointResponse.model_validate(e) for e in endpoints]

    async def delete_endpoint(
        self, endpoint_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        endpoint = await self.repo.get_endpoint(endpoint_id, user_id)
        if not endpoint:
            raise NotFoundError("Webhook endpoint")
        await self.repo.delete_endpoint(endpoint)