"""
app/api/v1/costs.py
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_admin_user, get_db
from app.domains.auth.models import User
from app.domains.costs.schemas import CostDashboardResponse
from app.domains.costs.service import CostService

router = APIRouter(prefix="/admin/costs", tags=["admin"])


@router.get("/dashboard", response_model=CostDashboardResponse)
async def cost_dashboard(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> CostDashboardResponse:
    service = CostService(db)
    return await service.get_dashboard()