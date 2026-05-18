"""
app/core/dependencies.py

FastAPI dependency injection. These are injected into route
handlers via Depends(). Keeps routes thin and testable.
"""

from typing import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidTokenError, PermissionDeniedError
from app.core.security import decode_token
from app.db.session import AsyncSessionFactory
from app.domains.auth.models import User
from app.domains.auth.repository import UserRepository

bearer_scheme = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session, auto-close on exit."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT and return the authenticated user."""
    payload = decode_token(credentials.credentials)

    if payload.get("type") != "access":
        raise InvalidTokenError("Expected access token")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise InvalidTokenError("Token missing subject")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)

    if not user:
        raise InvalidTokenError("User not found")
    if not user.is_active:
        raise PermissionDeniedError("Account is inactive")

    return user