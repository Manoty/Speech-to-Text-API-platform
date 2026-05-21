"""
tests/conftest.py — updated for Phase 5
Adds: cache mock fixture so tests don't hit real Redis
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock, patch

from app.core.config import settings
from app.db.base import Base
from app.main import create_app

TEST_DATABASE_URL = settings.database_url.replace(
    f"/{settings.postgres_db}", "/stt_test"
)

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionFactory = async_sessionmaker(engine_test, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db(setup_db) -> AsyncSession:
    async with TestSessionFactory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db) -> AsyncClient:
    from app.core.dependencies import get_db

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db

    # Mock cache so tests don't need Redis
    with patch("app.core.cache.cache.get", new_callable=AsyncMock, return_value=None), \
         patch("app.core.cache.cache.set", new_callable=AsyncMock), \
         patch("app.core.cache.cache.delete", new_callable=AsyncMock), \
         patch("app.core.cache.cache.get_transcript", new_callable=AsyncMock, return_value=None), \
         patch("app.core.cache.cache.set_transcript", new_callable=AsyncMock), \
         patch("app.core.cache.cache.invalidate_job", new_callable=AsyncMock), \
         patch("app.core.cache.cache.invalidate_transcript", new_callable=AsyncMock):

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c