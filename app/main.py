"""
app/main.py — updated for Phase 5
Adds: RequestIDMiddleware, Prometheus metrics, graceful shutdown
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.cache import cache
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.metrics import setup_metrics
from app.core.middleware import RateLimitMiddleware, RequestIDMiddleware
from app.db.session import engine

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── Startup ──────────────────────────────────────────────
    setup_logging()
    logger.info("application_starting", env=settings.app_env)
    os.makedirs(settings.upload_dir, exist_ok=True)

    yield

    # ── Shutdown ─────────────────────────────────────────────
    logger.info("application_shutting_down")

    # Close Redis cache connections
    await cache.close()

    # Dispose SQLAlchemy connection pool
    await engine.dispose()

    logger.info("application_shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Speech-to-Text Platform",
        version="1.0.0",
        description="Production-grade async transcription API",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware (order matters — first added = outermost) ─
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Prometheus metrics ───────────────────────────────────
    setup_metrics(app)

    # ── Exception handlers ───────────────────────────────────
    register_exception_handlers(app)

    # ── Routes ───────────────────────────────────────────────
    app.include_router(api_router)

    return app


app = create_app()