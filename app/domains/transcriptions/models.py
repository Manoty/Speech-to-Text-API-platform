"""
app/domains/transcriptions/models.py

Three models:
- UploadedFile: raw audio/video stored on disk
- TranscriptionJob: the async job with status tracking
- Transcript: the final result once job completes
"""

import enum
import uuid

from sqlalchemy import (
    BigInteger,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
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
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
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
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True
    )
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)  # hint, e.g. "en"
    model_size: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="jobs", lazy="noload")  # type: ignore[name-defined]
    uploaded_file: Mapped[UploadedFile] = relationship(
        "UploadedFile", back_populates="job", lazy="noload"
    )
    transcript: Mapped["Transcript | None"] = relationship(
        "Transcript", back_populates="job", lazy="noload"
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transcription_jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    language_detected: Mapped[str | None] = mapped_column(String(10), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    job: Mapped[TranscriptionJob] = relationship(
        "TranscriptionJob", back_populates="transcript", lazy="noload"
    )