"""
app/domains/transcriptions/schemas.py — updated for Phase 6
Adds: version fields, transcript history response
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.domains.transcriptions.models import JobStatus


class WordSegment(BaseModel):
    start: float
    end: float
    word: str
    probability: float | None = None


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
    segments: list[dict[str, Any]] | None
    version: int
    is_current: bool
    model_size: str
    created_at: datetime


class JobDetailResponse(BaseModel):
    model_config = {"from_attributes": True}

    job: TranscriptionJobResponse
    transcript: TranscriptResponse | None


class TranscriptHistoryResponse(BaseModel):
    job_id: uuid.UUID
    versions: list[TranscriptResponse]
    total_versions: int


class PaginatedJobsResponse(BaseModel):
    items: list[TranscriptionJobResponse]
    total: int
    page: int
    page_size: int
    pages: int


class TranscriptSearchResult(BaseModel):
    job_id: uuid.UUID
    transcript_id: uuid.UUID
    snippet: str
    language_detected: str | None
    created_at: datetime


class SearchResponse(BaseModel):
    items: list[TranscriptSearchResult]
    total: int
    query: str


class RetranscribeRequest(BaseModel):
    model_size: str = "base"
    language: str | None = None