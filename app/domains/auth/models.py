"""
app/domains/auth/models.py

User model. email is the unique login identifier.
is_active allows soft-disabling accounts without deletion.
"""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationship to transcription jobs (defined in transcriptions model)
    jobs: Mapped[list["TranscriptionJob"]] = relationship(  # type: ignore[name-defined]
        "TranscriptionJob", back_populates="user", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"