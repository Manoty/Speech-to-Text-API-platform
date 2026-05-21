"""
app/domains/quotas/service.py
"""

import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.domains.quotas.repository import QuotaRepository
from app.domains.quotas.schemas import QuotaResponse


class QuotaExceededError(AppException):
    def __init__(self, remaining: float) -> None:
        super().__init__(
            f"Monthly quota exceeded. {remaining:.1f} minutes remaining.",
            code="quota_exceeded",
        )


def _next_reset_date() -> date:
    today = date.today()
    if today.month == 12:
        return date(today.year + 1, 1, 1)
    return date(today.year, today.month + 1, 1)


class QuotaService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = QuotaRepository(db)

    async def get_or_create(self, user_id: uuid.UUID) -> QuotaResponse:
        quota = await self.repo.get_by_user_id(user_id)
        if not quota:
            quota = await self.repo.create(
                user_id=user_id,
                monthly_minutes_limit=settings.default_monthly_minutes,
                reset_date=_next_reset_date(),
            )
        return QuotaResponse.model_validate(quota)

    async def check_and_reserve(
        self, user_id: uuid.UUID, estimated_minutes: float
    ) -> None:
        """
        Called before starting a transcription job.
        Raises QuotaExceededError if user has insufficient quota.
        """
        if not settings.quota_enforcement_enabled:
            return

        quota = await self.repo.get_by_user_id(user_id)
        if not quota:
            quota = await self.repo.create(
                user_id=user_id,
                monthly_minutes_limit=settings.default_monthly_minutes,
                reset_date=_next_reset_date(),
            )

        # Check reset date — auto-reset if overdue
        if date.today() >= quota.reset_date:
            await self.repo.reset_all(_next_reset_date())
            quota = await self.repo.get_by_user_id(user_id)

        if quota and quota.minutes_remaining < estimated_minutes:
            raise QuotaExceededError(quota.minutes_remaining)

    async def record_usage(self, user_id: uuid.UUID, duration_seconds: float) -> None:
        """Called after transcription completes to record actual usage."""
        minutes = duration_seconds / 60
        await self.repo.add_usage(user_id, minutes)