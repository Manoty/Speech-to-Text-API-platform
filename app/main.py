"""
app/main.py — updated for Phase 3
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RateLimitMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    logger.info("application_starting", env=settings.app_env)
    os.makedirs(settings.upload_dir, exist_ok=True)
    yield
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Speech-to-Text Platform",
        version="1.0.0",
        description="Production-grade async transcription API",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RateLimitMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router)

    return app


app = create_app()