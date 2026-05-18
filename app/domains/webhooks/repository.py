"""
app/domains/webhooks/repository.py
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.webhooks.models import DeliveryStatus, WebhookDelivery, WebhookEndpoint


class WebhookRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_endpoint(
        self,
        user_id: uuid.UUID,
        url: str,
        secret: str | None,
        description: str | None,
    ) -> WebhookEndpoint:
        endpoint = WebhookEndpoint(
            user_id=user_id,
            url=url,
            secret=secret,
            description=description,
        )
        self.db.add(endpoint)
        await self.db.flush()
        return endpoint

    async def list_endpoints(self, user_id: uuid.UUID) -> list[WebhookEndpoint]:
        result = await self.db.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.user_id == user_id,
                WebhookEndpoint.is_active == True,
            )
        )
        return list(result.scalars().all())

    async def get_endpoint(
        self, endpoint_id: uuid.UUID, user_id: uuid.UUID
    ) -> WebhookEndpoint | None:
        result = await self.db.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.id == endpoint_id,
                WebhookEndpoint.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_endpoint(self, endpoint: WebhookEndpoint) -> None:
        endpoint.is_active = False
        await self.db.flush()

    async def get_active_endpoints_for_user(
        self, user_id: uuid.UUID
    ) -> list[WebhookEndpoint]:
        result = await self.db.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.user_id == user_id,
                WebhookEndpoint.is_active == True,
            )
        )
        return list(result.scalars().all())

    async def create_delivery(
        self,
        endpoint_id: uuid.UUID,
        job_id: uuid.UUID,
        status: DeliveryStatus,
        http_status_code: int | None = None,
        response_body: str | None = None,
        attempt_number: int = 1,
        error_message: str | None = None,
    ) -> WebhookDelivery:
        delivery = WebhookDelivery(
            endpoint_id=endpoint_id,
            job_id=job_id,
            status=status,
            http_status_code=http_status_code,
            response_body=response_body,
            attempt_number=attempt_number,
            error_message=error_message,
        )
        self.db.add(delivery)
        await self.db.flush()
        return delivery