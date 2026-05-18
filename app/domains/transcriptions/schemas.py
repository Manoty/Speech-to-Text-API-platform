"""
app/domains/transcriptions/schemas.py
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.domains.transcriptions.models import JobStatus


class TranscriptionJobResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    status: JobStatus
    language: str | None
    model_size: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class TranscriptResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    job_id: uuid.UUID
    full_text: str
    language_detected: str | None
    duration_seconds: float | None
    processing_time_seconds: float | None
    word_count: int
    created_at: datetime


class JobDetailResponse(BaseModel):
    model_config = {"from_attributes": True}

    job: TranscriptionJobResponse
    transcript: TranscriptResponse | None


class PaginatedJobsResponse(BaseModel):
    items: list[TranscriptionJobResponse]
    total: int
    page: int
    page_size: int
    pages: int