import pytest
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.quotas.service import QuotaService, QuotaExceededError


@pytest.mark.asyncio
async def test_get_or_create_quota(client, db: AsyncSession):
    from app.domains.auth.models import User
    import uuid

    user = User(
        email="quota@example.com",
        hashed_password="hashed",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    service = QuotaService(db)
    quota = await service.get_or_create(user.id)

    assert quota.monthly_minutes_limit == 300
    assert quota.minutes_used_this_month == 0.0
    assert quota.minutes_remaining == 300.0
    assert quota.is_exceeded is False


@pytest.mark.asyncio
async def test_quota_exceeded(client, db: AsyncSession):
    from app.domains.auth.models import User
    from app.domains.quotas.models import UserQuota

    user = User(
        email="quotamax@example.com",
        hashed_password="hashed",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    quota = UserQuota(
        user_id=user.id,
        monthly_minutes_limit=10,
        minutes_used_this_month=10.0,
        reset_date=date(2099, 1, 1),
    )
    db.add(quota)
    await db.flush()

    service = QuotaService(db)
    with pytest.raises(QuotaExceededError):
        await service.check_and_reserve(user.id, estimated_minutes=1.0)