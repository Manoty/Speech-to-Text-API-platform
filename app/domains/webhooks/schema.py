"""
app/domains/webhooks/schemas.py
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class WebhookEndpointCreate(BaseModel):
    url: HttpUrl
    secret: str | None = None
    description: str | None = None


class WebhookEndpointResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    url: str
    is_active: bool
    description: str | None
    created_at: datetime


class WebhookDeliveryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    endpoint_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    http_status_code: int | None
    attempt_number: int
    error_message: str | None
    created_at: datetime