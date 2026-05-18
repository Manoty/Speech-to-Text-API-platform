"""
app/main.py

FastAPI application factory.

WHY factory pattern (create_app)?
- Enables creating isolated app instances in tests
- Clean startup/shutdown lifecycle
- Single place for all middleware and handler registration
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown logic."""
    setup_logging()
    logger.info("application_starting", env=settings.app_env)

    # Ensure upload directory exists
    import os
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

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    register_exception_handlers(app)

    # Routes
    app.include_router(api_router)

    return app


app = create_app()