"""
app/domains/apikeys/repository.py
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.apikeys.models import ApiKey


class ApiKeyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        name: str,
        key_hash: str,
        key_prefix: str,
    ) -> ApiKey:
        api_key = ApiKey(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
        )
        self.db.add(api_key)
        await self.db.flush()
        return api_key

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        result = await self.db.execute(
            select(ApiKey)
            .where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
            .options(selectinload(ApiKey.user))
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[ApiKey]:
        result = await self.db.execute(
            select(ApiKey)
            .where(ApiKey.user_id == user_id, ApiKey.is_active == True)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, key_id: uuid.UUID, user_id: uuid.UUID
    ) -> ApiKey | None:
        result = await self.db.execute(
            select(ApiKey).where(
                ApiKey.id == key_id,
                ApiKey.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def revoke(self, api_key: ApiKey) -> None:
        api_key.is_active = False
        await self.db.flush()

    async def record_last_used(self, key_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        api_key = result.scalar_one_or_none()
        if api_key:
            api_key.last_used_at = datetime.now(timezone.utc)
            await self.db.flush()