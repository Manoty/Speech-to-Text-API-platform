"""
app/core/dependencies.py — updated for Phase 4

Auth now accepts EITHER:
  - Bearer JWT token (Authorization: Bearer <token>)
  - API key header   (X-API-Key: <key>)

WHY dual auth?
JWT is for human users via browser/app.
API keys are for server-to-server integrations where
managing token refresh is impractical.
"""

import hashlib
from typing import AsyncGenerator

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import InvalidTokenError, PermissionDeniedError
from app.core.security import decode_token
from app.db.session import AsyncSessionFactory
from app.domains.auth.models import User
from app.domains.auth.repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _user_from_jwt(token: str, db: AsyncSession) -> User | None:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user_id: str | None = payload.get("sub")
        if not user_id:
            return None
        repo = UserRepository(db)
        return await repo.get_by_id(user_id)
    except Exception:
        return None


async def _user_from_api_key(raw_key: str, db: AsyncSession) -> User | None:
    from app.domains.apikeys.repository import ApiKeyRepository
    hashed = hashlib.sha256(raw_key.encode()).hexdigest()
    repo = ApiKeyRepository(db)
    api_key = await repo.get_by_hash(hashed)
    if not api_key or not api_key.is_active:
        return None
    await repo.record_last_used(api_key.id)
    return api_key.user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user: User | None = None

    # Try JWT first
    if credentials and credentials.scheme.lower() == "bearer":
        user = await _user_from_jwt(credentials.credentials, db)

    # Try API key if JWT didn't work
    if user is None:
        api_key_value = request.headers.get(settings.api_key_header_name)
        if api_key_value:
            user = await _user_from_api_key(api_key_value, db)

    if user is None:
        raise InvalidTokenError("Valid authentication credentials required")

    if not user.is_active:
        raise PermissionDeniedError("Account is inactive")

    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise PermissionDeniedError("Admin access required")
    return current_user