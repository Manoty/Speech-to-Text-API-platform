"""
app/domains/audit/service.py

Thin service wrapping audit repository.
Called from routes after significant actions.

Audit actions tracked:
    user.register
    user.login
    user.login_failed
    apikey.created
    apikey.revoked
    transcription.uploaded
    transcription.completed
    transcription.failed
    webhook.created
    webhook.deleted
"""

import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.repository import AuditRepository


def _extract_request_meta(request: Request) -> dict:
    forwarded = request.headers.get("X-Forwarded-For")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    return {
        "ip_address": ip,
        "user_agent": request.headers.get("User-Agent"),
        "request_id": request.headers.get("X-Request-ID"),
    }


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = AuditRepository(db)

    async def log(
        self,
        action: str,
        request: Request | None = None,
        user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        meta = _extract_request_meta(request) if request else {}
        await self.repo.log(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent"),
            request_id=meta.get("request_id"),
            metadata=metadata,
        )