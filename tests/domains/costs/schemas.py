"""
app/domains/costs/schemas.py
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ComputeCostResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    job_id: uuid.UUID
    model_size: str
    audio_duration_seconds: float
    processing_time_seconds: float
    estimated_cost_usd: float
    created_at: datetime


class UserCostSummary(BaseModel):
    user_id: str
    email: str
    total_jobs: int
    total_audio_hours: float
    total_cost_usd: float
    avg_cost_per_job_usd: float


class MonthlyCostSummary(BaseModel):
    year: int
    month: int
    total_jobs: int
    total_audio_hours: float
    total_cost_usd: float


class CostDashboardResponse(BaseModel):
    total_cost_usd: float
    total_audio_hours: float
    total_jobs: int
    by_model: dict[str, float]
    top_users: list[UserCostSummary]
    monthly_trend: list[MonthlyCostSummary]