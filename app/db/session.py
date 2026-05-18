"""
app/db/session.py

Async SQLAlchemy engine + session factory.

WHY async? FastAPI is async-first. Blocking DB calls
in async routes would kill concurrency.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,   # logs all SQL in debug mode
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,        # drop stale connections automatically
)

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,    # avoid lazy-load errors after commit
    autocommit=False,
    autoflush=False,
)