"""
app/domains/auth/models.py
"""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    jobs: Mapped[list["TranscriptionJob"]] = relationship(  # type: ignore[name-defined]
        "TranscriptionJob", back_populates="user", lazy="noload"
    )
    webhook_endpoints: Mapped[list["WebhookEndpoint"]] = relationship(  # type: ignore[name-defined]
        "WebhookEndpoint", back_populates="user", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"