"""
app/core/middleware.py

Rate limiting via Redis sliding window counter.

WHY sliding window vs fixed window?
Fixed window allows 2x burst at window boundaries.
Sliding window distributes requests evenly over time.

Limits (configurable):
- Authenticated users: 100 requests / 60 seconds
- Upload endpoint: 10 uploads / 60 seconds (heavier resource)
"""

import time

import redis.asyncio as aioredis
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Stricter limits per route prefix
ROUTE_LIMITS: dict[str, tuple[int, int]] = {
    # (max_requests, window_seconds)
    "/api/v1/transcriptions/upload": (10, 60),
    "/api/v1/auth/login": (10, 60),
    "/api/v1/auth/register": (5, 60),
}
DEFAULT_LIMIT = (100, 60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str = settings.redis_url) -> None:
        super().__init__(app)
        self.redis = aioredis.from_url(redis_url, decode_responses=True)

    async def dispatch(self, request: Request, call_next):
        # Determine identifier: prefer user id from token, fallback to IP
        identifier = self._get_identifier(request)
        path = request.url.path

        max_requests, window = self._get_limit(path)
        key = f"rl:{identifier}:{path}"

        now = time.time()
        window_start = now - window

        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, window)
            results = await pipe.execute()

        request_count = results[1]

        if request_count >= max_requests:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                path=path,
                count=request_count,
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. Max {max_requests} per {window}s.",
                },
                headers={"Retry-After": str(window)},
            )

        return await call_next(request)

    def _get_identifier(self, request: Request) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            # Use token suffix as identifier (not decoded, just fingerprinting)
            return f"token:{auth[-16:]}"
        forwarded = request.headers.get("X-Forwarded-For")
        ip = forwarded.split(",")[0] if forwarded else (request.client.host if request.client else "unknown")
        return f"ip:{ip}"

    def _get_limit(self, path: str) -> tuple[int, int]:
        for prefix, limit in ROUTE_LIMITS.items():
            if path.startswith(prefix):
                return limit
        return DEFAULT_LIMIT