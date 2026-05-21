"""
app/core/middleware.py — updated for Phase 5

Added: RequestIDMiddleware
Every request gets a UUID. Bound to structlog context so
every log line carries request_id automatically.
Also returned in response header X-Request-ID for client tracing.
"""

import time
import uuid

import redis.asyncio as aioredis
import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ROUTE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/transcriptions/upload": (10, 60),
    "/api/v1/auth/login": (10, 60),
    "/api/v1/auth/register": (5, 60),
}
DEFAULT_LIMIT = (100, 60)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Generates a unique request_id for every request.
    Binds it to structlog context so all logs in the request carry it.
    Returns it in X-Request-ID response header.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())

        # Bind to structlog context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str = settings.redis_url) -> None:
        super().__init__(app)
        self.redis = aioredis.from_url(redis_url, decode_responses=True)

    async def dispatch(self, request: Request, call_next):
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
            return f"token:{auth[-16:]}"
        forwarded = request.headers.get("X-Forwarded-For")
        ip = (
            forwarded.split(",")[0]
            if forwarded
            else (request.client.host if request.client else "unknown")
        )
        return f"ip:{ip}"

    def _get_limit(self, path: str) -> tuple[int, int]:
        for prefix, limit in ROUTE_LIMITS.items():
            if path.startswith(prefix):
                return limit
        return DEFAULT_LIMIT