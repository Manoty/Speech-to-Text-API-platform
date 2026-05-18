"""
app/domains/auth/service.py

Business logic for authentication.
Raises domain exceptions — never HTTPException.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.exceptions import InvalidTokenError
from app.domains.auth.repository import UserRepository
from app.domains.auth.schemas import TokenResponse, UserResponse


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = UserRepository(db)

    async def register(
        self, email: str, password: str, full_name: str | None
    ) -> UserResponse:
        existing = await self.repo.get_by_email(email)
        if existing:
            raise ConflictError("An account with this email already exists")

        user = await self.repo.create(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
        )
        return UserResponse.model_validate(user)

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self.repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account is inactive")

        return TokenResponse(
            access_token=create_access_token(subject=str(user.id)),
            refresh_token=create_refresh_token(subject=str(user.id)),
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise InvalidTokenError("Expected refresh token")

        user_id: str | None = payload.get("sub")
        if not user_id:
            raise InvalidTokenError("Token missing subject")

        user = await self.repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise InvalidTokenError("User not found or inactive")

        return TokenResponse(
            access_token=create_access_token(subject=str(user.id)),
            refresh_token=create_refresh_token(subject=str(user.id)),
        )