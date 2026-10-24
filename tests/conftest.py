"""Pytest fixtures and configuration."""

from collections.abc import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import Settings, get_settings
from src.database.base import Base
from src.database.session import async_session_factory, engine, init_db
from src.main import app
from src.webhook.deduplicator import deduplicator

TEST_DB_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Fixture providing deterministic test configuration."""
    return Settings(
        APP_ENV="testing",
        META_VERIFY_TOKEN="test_verify_token_123",
        META_APP_SECRET="test_meta_app_secret_abc456",
        DATABASE_URL=TEST_DB_URL,
        LLM_PROVIDER="mock",
        CALENDAR_PROVIDER="mock",
        CRM_PROVIDER="mock",
    )


@pytest.fixture(autouse=True)
async def clean_database():
    """Ensure database tables and deduplicator cache are fresh before each test."""
    await init_db()
    deduplicator._cache.clear()
    async with async_session_factory() as session:
        # Clear tables in order of foreign key dependency
        for tbl in ["messages", "bookings", "handoff_escalations", "outbox_events", "audit_events", "conversations", "leads"]:
            await session.execute(text(f"DELETE FROM {tbl}"))
        await session.commit()
    yield
    deduplicator._cache.clear()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a fresh isolated database session."""
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def async_client(test_settings) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client configured to make requests against FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
