"""
app/domains/analytics/service.py

Admin analytics — aggregate queries.
Only accessible to is_admin=True users (enforced at route level).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.analytics.schemas import PlatformStats, TopUsersResponse, UserUsageStats
from app.domains.auth.models import User
from app.domains.transcriptions.models import JobStatus, Transcript, TranscriptionJob


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_platform_stats(self) -> PlatformStats:
        total_users = await self.db.scalar(select(func.count(User.id)))
        total_jobs = await self.db.scalar(select(func.count(TranscriptionJob.id)))

        completed = await self.db.scalar(
            select(func.count(TranscriptionJob.id)).where(
                TranscriptionJob.status == JobStatus.COMPLETED
            )
        )
        failed = await self.db.scalar(
            select(func.count(TranscriptionJob.id)).where(
                TranscriptionJob.status == JobStatus.FAILED
            )
        )
        pending = await self.db.scalar(
            select(func.count(TranscriptionJob.id)).where(
                TranscriptionJob.status == JobStatus.PENDING
            )
        )
        total_transcripts = await self.db.scalar(select(func.count(Transcript.id)))
        total_seconds = await self.db.scalar(
            select(func.coalesce(func.sum(Transcript.duration_seconds), 0))
        )

        return PlatformStats(
            total_users=total_users or 0,
            total_jobs=total_jobs or 0,
            completed_jobs=completed or 0,
            failed_jobs=failed or 0,
            pending_jobs=pending or 0,
            total_transcripts=total_transcripts or 0,
            total_audio_hours=round((total_seconds or 0) / 3600, 2),
        )

    async def get_top_users(self, limit: int = 20) -> TopUsersResponse:
        result = await self.db.execute(
            select(
                User.id,
                User.email,
                func.count(TranscriptionJob.id).label("total_jobs"),
                func.sum(
                    func.cast(TranscriptionJob.status == JobStatus.COMPLETED, type_=func.Integer)
                ).label("completed_jobs"),
                func.sum(
                    func.cast(TranscriptionJob.status == JobStatus.FAILED, type_=func.Integer)
                ).label("failed_jobs"),
                func.coalesce(func.sum(Transcript.duration_seconds), 0).label("total_audio_seconds"),
                func.coalesce(func.sum(Transcript.word_count), 0).label("total_words"),
            )
            .join(TranscriptionJob, TranscriptionJob.user_id == User.id, isouter=True)
            .join(Transcript, Transcript.job_id == TranscriptionJob.id, isouter=True)
            .group_by(User.id, User.email)
            .order_by(func.count(TranscriptionJob.id).desc())
            .limit(limit)
        )

        rows = result.all()
        return TopUsersResponse(
            users=[
                UserUsageStats(
                    user_id=str(row.id),
                    email=row.email,
                    total_jobs=row.total_jobs or 0,
                    completed_jobs=int(row.completed_jobs or 0),
                    failed_jobs=int(row.failed_jobs or 0),
                    total_audio_seconds=float(row.total_audio_seconds or 0),
                    total_words_transcribed=int(row.total_words or 0),
                )
                for row in rows
            ]
        )