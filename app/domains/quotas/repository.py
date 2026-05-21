"""
app/domains/quotas/repository.py
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.quotas.models import UserQuota


class QuotaRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_user_id(self, user_id: uuid.UUID) -> UserQuota | None:
        result = await self.db.execute(
            select(UserQuota).where(UserQuota.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: uuid.UUID,
        monthly_minutes_limit: int,
        reset_date: date,
    ) -> UserQuota:
        quota = UserQuota(
            user_id=user_id,
            monthly_minutes_limit=monthly_minutes_limit,
            minutes_used_this_month=0.0,
            reset_date=reset_date,
        )
        self.db.add(quota)
        await self.db.flush()
        return quota

    async def add_usage(self, user_id: uuid.UUID, minutes: float) -> None:
        result = await self.db.execute(
            select(UserQuota).where(UserQuota.user_id == user_id)
        )
        quota = result.scalar_one_or_none()
        if quota:
            quota.minutes_used_this_month += minutes
            await self.db.flush()

    async def reset_all(self, new_reset_date: date) -> int:
        """Reset all users' monthly usage. Returns count reset."""
        result = await self.db.execute(select(UserQuota))
        quotas = result.scalars().all()
        for quota in quotas:
            quota.minutes_used_this_month = 0.0
            quota.reset_date = new_reset_date
        await self.db.flush()
        return len(quotas)