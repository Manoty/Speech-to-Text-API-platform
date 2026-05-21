"""
app/domains/quotas/schemas.py
"""

from datetime import date

from pydantic import BaseModel


class QuotaResponse(BaseModel):
    model_config = {"from_attributes": True}

    monthly_minutes_limit: int
    minutes_used_this_month: float
    minutes_remaining: float
    reset_date: date
    is_exceeded: bool