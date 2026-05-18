"""
app/api/v1/analytics.py
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_admin_user, get_db
from app.domains.auth.models import User
from app.domains.analytics.schemas import PlatformStats, TopUsersResponse
from app.domains.analytics.service import AnalyticsService

router = APIRouter(prefix="/admin/analytics", tags=["admin"])


@router.get("/stats", response_model=PlatformStats)
async def platform_stats(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformStats:
    service = AnalyticsService(db)
    return await service.get_platform_stats()


@router.get("/top-users", response_model=TopUsersResponse)
async def top_users(
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> TopUsersResponse:
    service = AnalyticsService(db)
    return await service.get_top_users(limit=limit)