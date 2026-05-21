"""
app/domains/quotas/models.py

UserQuota: tracks monthly audio minutes used per user.
Resets on the 1st of each month via Celery Beat.

WHY store minutes not seconds?
More human-readable in admin dashboards and error messages.
Internally we convert from seconds when recording usage.
"""

import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserQuota(Base):
    __tablename__ = "user_quotas"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    monthly_minutes_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300
    )
    minutes_used_this_month: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    reset_date: Mapped[date] = mapped_column(Date, nullable=False)

    user: Mapped["User"] = relationship("User", lazy="noload")  # type: ignore[name-defined]

    @property
    def minutes_remaining(self) -> float:
        return max(0.0, self.monthly_minutes_limit - self.minutes_used_this_month)

    @property
    def is_exceeded(self) -> bool:
        return self.minutes_used_this_month >= self.monthly_minutes_limit