"""
app/domains/costs/repository.py
"""

import uuid

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.costs.models import ComputeCost
from app.domains.auth.models import User


class CostRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        job_id: uuid.UUID,
        user_id: uuid.UUID,
        model_size: str,
        audio_duration_seconds: float,
        processing_time_seconds: float,
        estimated_cost_usd: float,
    ) -> ComputeCost:
        cost = ComputeCost(
            job_id=job_id,
            user_id=user_id,
            model_size=model_size,
            audio_duration_seconds=audio_duration_seconds,
            processing_time_seconds=processing_time_seconds,
            estimated_cost_usd=estimated_cost_usd,
        )
        self.db.add(cost)
        await self.db.flush()
        return cost

    async def get_by_job(self, job_id: uuid.UUID) -> ComputeCost | None:
        result = await self.db.execute(
            select(ComputeCost).where(ComputeCost.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_user_total(self, user_id: uuid.UUID) -> float:
        result = await self.db.execute(
            select(func.coalesce(func.sum(ComputeCost.estimated_cost_usd), 0.0))
            .where(ComputeCost.user_id == user_id)
        )
        return float(result.scalar_one())

    async def get_top_users_by_cost(self, limit: int = 10) -> list[dict]:
        result = await self.db.execute(
            select(
                User.id,
                User.email,
                func.count(ComputeCost.id).label("total_jobs"),
                func.coalesce(
                    func.sum(ComputeCost.audio_duration_seconds), 0.0
                ).label("total_seconds"),
                func.coalesce(
                    func.sum(ComputeCost.estimated_cost_usd), 0.0
                ).label("total_cost"),
            )
            .join(ComputeCost, ComputeCost.user_id == User.id, isouter=True)
            .group_by(User.id, User.email)
            .order_by(func.sum(ComputeCost.estimated_cost_usd).desc().nullslast())
            .limit(limit)
        )
        return [dict(row._mapping) for row in result.all()]

    async def get_monthly_trend(self, months: int = 6) -> list[dict]:
        result = await self.db.execute(
            select(
                extract("year", ComputeCost.created_at).label("year"),
                extract("month", ComputeCost.created_at).label("month"),
                func.count(ComputeCost.id).label("total_jobs"),
                func.coalesce(
                    func.sum(ComputeCost.audio_duration_seconds), 0.0
                ).label("total_seconds"),
                func.coalesce(
                    func.sum(ComputeCost.estimated_cost_usd), 0.0
                ).label("total_cost"),
            )
            .group_by("year", "month")
            .order_by("year", "month")
            .limit(months)
        )
        return [dict(row._mapping) for row in result.all()]

    async def get_cost_by_model(self) -> dict[str, float]:
        result = await self.db.execute(
            select(
                ComputeCost.model_size,
                func.coalesce(
                    func.sum(ComputeCost.estimated_cost_usd), 0.0
                ).label("total"),
            )
            .group_by(ComputeCost.model_size)
        )
        return {row.model_size: float(row.total) for row in result.all()}

    async def get_platform_total(self) -> float:
        result = await self.db.execute(
            select(func.coalesce(func.sum(ComputeCost.estimated_cost_usd), 0.0))
        )
        return float(result.scalar_one())