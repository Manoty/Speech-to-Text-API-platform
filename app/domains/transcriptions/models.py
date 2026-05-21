"""
app/domains/transcriptions/models.py — updated for Phase 6

Changes:
- Transcript gains version + is_current fields
- Enables re-transcription with version history
"""

import enum
import uuid

from sqlalchemy import (
    BigInteger, Boolean, Enum, Float, ForeignKey,
    Index, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    user: Mapped["User"] = relationship("User", lazy="noload")  # type: ignore[name-defined]
    job: Mapped["TranscriptionJob | None"] = relationship(
        "TranscriptionJob", back_populates="uploaded_file", lazy="noload"
    )


class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True
    )
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    model_size: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="jobs", lazy="noload"
    )
    uploaded_file: Mapped[UploadedFile] = relationship(
        "UploadedFile", back_populates="job", lazy="noload"
    )
    transcripts: Mapped[list["Transcript"]] = relationship(
        "Transcript", back_populates="job", lazy="noload",
        order_by="Transcript.version.desc()",
    )

    @property
    def transcript(self) -> "Transcript | None":
        """Returns the current (latest) transcript version."""
        for t in self.transcripts:
            if t.is_current:
                return t
        return self.transcripts[0] if self.transcripts else None


class Transcript(Base):
    __tablename__ = "transcripts"

    __table_args__ = (
        Index("ix_transcripts_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_transcripts_job_current", "job_id", "is_current"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transcription_jobs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    language_detected: Mapped[str | None] = mapped_column(String(10), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    segments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    # Versioning fields
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    model_size: Mapped[str] = mapped_column(String(20), nullable=False, default="base")

    job: Mapped[TranscriptionJob] = relationship(
        "TranscriptionJob", back_populates="transcripts", lazy="noload"
    )