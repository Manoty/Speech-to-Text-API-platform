"""
app/api/v1/transcriptions.py — updated for Phase 4
Adds: search endpoint, export endpoint (SRT/VTT/TXT)
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.domains.auth.models import User
from app.domains.transcriptions.models import JobStatus
from app.domains.transcriptions.schemas import (
    JobDetailResponse,
    PaginatedJobsResponse,
    SearchResponse,
    TranscriptionJobResponse,
)
from app.domains.transcriptions.service import TranscriptionService

router = APIRouter(prefix="/transcriptions", tags=["transcriptions"])


@router.post(
    "/upload",
    response_model=TranscriptionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_audio(
    file: UploadFile = File(...),
    language: str | None = Form(None),
    model_size: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranscriptionJobResponse:
    service = TranscriptionService(db)
    return await service.upload_and_create_job(
        user_id=current_user.id,
        file=file,
        language=language,
        model_size=model_size,
    )


@router.get("/search", response_model=SearchResponse)
async def search_transcripts(
    q: str = Query(..., min_length=2, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    service = TranscriptionService(db)
    return await service.search(
        user_id=current_user.id,
        query=q,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}/export")
async def export_transcript(
    job_id: uuid.UUID,
    format: str = Query("srt", pattern="^(srt|vtt|txt)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    service = TranscriptionService(db)
    content, media_type, filename = await service.export(
        job_id=job_id,
        user_id=current_user.id,
        format=format,
    )
    return PlainTextResponse(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobDetailResponse:
    service = TranscriptionService(db)
    return await service.get_job(job_id=job_id, user_id=current_user.id)


@router.get("/", response_model=PaginatedJobsResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: JobStatus | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedJobsResponse:
    service = TranscriptionService(db)
    return await service.list_jobs(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status=status,
    )