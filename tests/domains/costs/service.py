"""
app/domains/costs/service.py
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.costs.models import MODEL_COST_PER_MINUTE, ComputeCost
from app.domains.costs.repository import CostRepository
from app.domains.costs.schemas import (
    CostDashboardResponse,
    MonthlyCostSummary,
    UserCostSummary,
)


def calculate_cost(
    model_size: str, audio_duration_seconds: float
) -> float:
    rate = MODEL_COST_PER_MINUTE.get(model_size, 0.002)
    minutes = audio_duration_seconds / 60
    return round(rate * minutes, 6)


class CostService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = CostRepository(db)

    async def record_cost(
        self,
        job_id: uuid.UUID,
        user_id: uuid.UUID,
        model_size: str,
        audio_duration_seconds: float,
        processing_time_seconds: float,
    ) -> ComputeCost:
        estimated_cost = calculate_cost(model_size, audio_duration_seconds)
        return await self.repo.create(
            job_id=job_id,
            user_id=user_id,
            model_size=model_size,
            audio_duration_seconds=audio_duration_seconds,
            processing_time_seconds=processing_time_seconds,
            estimated_cost_usd=estimated_cost,
        )

    async def get_dashboard(self) -> CostDashboardResponse:
        total_cost = await self.repo.get_platform_total()
        by_model = await self.repo.get_cost_by_model()
        top_users_raw = await self.repo.get_top_users_by_cost(limit=10)
        monthly_raw = await self.repo.get_monthly_trend(months=6)

        top_users = [
            UserCostSummary(
                user_id=str(row["id"]),
                email=row["email"],
                total_jobs=row["total_jobs"] or 0,
                total_audio_hours=round(
                    float(row["total_seconds"] or 0) / 3600, 2
                ),
                total_cost_usd=round(float(row["total_cost"] or 0), 4),
                avg_cost_per_job_usd=round(
                    float(row["total_cost"] or 0) / max(row["total_jobs"] or 1, 1), 4
                ),
            )
            for row in top_users_raw
        ]

        monthly = [
            MonthlyCostSummary(
                year=int(row["year"]),
                month=int(row["month"]),
                total_jobs=row["total_jobs"] or 0,
                total_audio_hours=round(
                    float(row["total_seconds"] or 0) / 3600, 2
                ),
                total_cost_usd=round(float(row["total_cost"] or 0), 4),
            )
            for row in monthly_raw
        ]

        total_hours = sum(u.total_audio_hours for u in top_users)
        total_jobs = sum(u.total_jobs for u in top_users)

        return CostDashboardResponse(
            total_cost_usd=round(total_cost, 4),
            total_audio_hours=total_hours,
            total_jobs=total_jobs,
            by_model=by_model,
            top_users=top_users,
            monthly_trend=monthly,
        )