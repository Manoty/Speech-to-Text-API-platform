"""
app/domains/apikeys/service.py

Generates a cryptographically secure API key, stores only the hash.
Format: stt_<32 random hex chars>
"""

import hashlib
import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.apikeys.repository import ApiKeyRepository
from app.domains.apikeys.schemas import ApiKeyCreatedResponse, ApiKeyResponse


KEY_PREFIX = "stt_"


def _generate_raw_key() -> str:
    return KEY_PREFIX + secrets.token_hex(32)


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class ApiKeyService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = ApiKeyRepository(db)

    async def create_key(
        self, user_id: uuid.UUID, name: str
    ) -> ApiKeyCreatedResponse:
        raw_key = _generate_raw_key()
        key_hash = _hash_key(raw_key)
        key_prefix = raw_key[:8]  # "stt_XXXX"

        api_key = await self.repo.create(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
        )

        return ApiKeyCreatedResponse(
            id=api_key.id,
            name=api_key.name,
            key_prefix=key_prefix,
            raw_key=raw_key,
            created_at=api_key.created_at,
        )

    async def list_keys(self, user_id: uuid.UUID) -> list[ApiKeyResponse]:
        keys = await self.repo.list_by_user(user_id)
        return [ApiKeyResponse.model_validate(k) for k in keys]

    async def revoke_key(self, key_id: uuid.UUID, user_id: uuid.UUID) -> None:
        api_key = await self.repo.get_by_id(key_id, user_id)
        if not api_key:
            raise NotFoundError("API key")
        await self.repo.revoke(api_key)