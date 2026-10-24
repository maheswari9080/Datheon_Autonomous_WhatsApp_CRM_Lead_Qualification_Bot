"""Pytest fixtures and configuration."""

from collections.abc import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import Settings, get_settings
from src.database.base import Base
from src.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


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


@pytest.fixture
async def test_engine():
    """Async engine tied to an in-memory database."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provides a fresh isolated database session."""
    session_maker = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session


@pytest.fixture
async def async_client(test_settings) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client configured to make requests against FastAPI app."""
    # Override settings singleton
    app.dependency_overrides = {}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
