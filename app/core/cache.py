"""
app/core/cache.py

Redis cache abstraction.

WHY a wrapper and not raw redis calls in services?
- Single place to change TTLs
- Easy to mock in tests
- Consistent key naming
- One place to disable caching entirely

Key schema:
    cache:transcript:{job_id}     TTL: 1 hour
    cache:job_status:{job_id}     TTL: 30 seconds
    cache:user:{user_id}          TTL: 5 minutes
"""

import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# TTLs in seconds
TTL_TRANSCRIPT = 3600       # 1 hour — completed transcripts rarely change
TTL_JOB_STATUS = 30         # 30 seconds — status changes during processing
TTL_USER = 300              # 5 minutes


def _make_key(*parts: str) -> str:
    return ":".join(["cache"] + list(parts))


class RedisCache:
    def __init__(self) -> None:
        self._client: aioredis.Redis | None = None

    async def client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
                encoding="utf-8",
            )
        return self._client

    async def get(self, key: str) -> Any | None:
        try:
            r = await self.client()
            value = await r.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as exc:
            logger.warning("cache_get_failed", key=key, error=str(exc))
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            r = await self.client()
            await r.setex(key, ttl, json.dumps(value, default=str))
        except Exception as exc:
            logger.warning("cache_set_failed", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        try:
            r = await self.client()
            await r.delete(key)
        except Exception as exc:
            logger.warning("cache_delete_failed", key=key, error=str(exc))

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Domain-specific helpers ──────────────────────────────

    def transcript_key(self, job_id: str) -> str:
        return _make_key("transcript", job_id)

    def job_status_key(self, job_id: str) -> str:
        return _make_key("job_status", job_id)

    def user_key(self, user_id: str) -> str:
        return _make_key("user", user_id)

    async def get_transcript(self, job_id: str) -> dict | None:
        return await self.get(self.transcript_key(job_id))

    async def set_transcript(self, job_id: str, data: dict) -> None:
        await self.set(self.transcript_key(job_id), data, TTL_TRANSCRIPT)

    async def invalidate_transcript(self, job_id: str) -> None:
        await self.delete(self.transcript_key(job_id))

    async def get_job_status(self, job_id: str) -> dict | None:
        return await self.get(self.job_status_key(job_id))

    async def set_job_status(self, job_id: str, data: dict) -> None:
        await self.set(self.job_status_key(job_id), data, TTL_JOB_STATUS)

    async def invalidate_job(self, job_id: str) -> None:
        await self.delete(self.job_status_key(job_id))
        await self.delete(self.transcript_key(job_id))


# Module-level singleton
cache = RedisCache()