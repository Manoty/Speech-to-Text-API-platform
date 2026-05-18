"""
app/domains/analytics/schemas.py
"""

from pydantic import BaseModel


class PlatformStats(BaseModel):
    total_users: int
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    pending_jobs: int
    total_transcripts: int
    total_audio_hours: float


class UserUsageStats(BaseModel):
    user_id: str
    email: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_audio_seconds: float
    total_words_transcribed: int


class TopUsersResponse(BaseModel):
    users: list[UserUsageStats]