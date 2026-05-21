"""
app/domains/costs/models.py

ComputeCost records the actual cost of each completed transcription.
Cost is estimated based on: model size, audio duration, processing time.

WHY track costs in DB?
Enables per-user billing, org cost allocation,
admin dashboards, and future usage-based pricing.
"""

import uuid

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# Cost per minute of audio by model size (USD)
MODEL_COST_PER_MINUTE: dict[str, float] = {
    "tiny":     0.001,
    "base":     0.002,
    "small":    0.004,
    "medium":   0.008,
    "large-v3": 0.015,
}


class ComputeCost(Base):
    __tablename__ = "compute_costs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transcription_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_size: Mapped[str] = mapped_column(String(20), nullable=False)
    audio_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    processing_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False)

    job: Mapped["TranscriptionJob"] = relationship(  # type: ignore[name-defined]
        "TranscriptionJob", lazy="noload"
    )
    user: Mapped["User"] = relationship("User", lazy="noload")  # type: ignore[name-defined]