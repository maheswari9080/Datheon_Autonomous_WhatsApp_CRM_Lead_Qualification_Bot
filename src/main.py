"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import get_settings
from src.core.logging import correlation_id_ctx, get_logger, setup_logging
from src.database.session import close_db, init_db
from src.webhook.router import webhook_router

settings = get_settings()
setup_logging(log_level=settings.LOG_LEVEL)
logger = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assigns or propagates X-Correlation-ID for every incoming HTTP request."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        correlation_id_ctx.set(correlation_id)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle manager."""
    logger.info(f"Starting {settings.APP_NAME} in [{settings.APP_ENV}] mode")
    # Initialize database tables in dev/testing mode
    if settings.APP_ENV != "production":
        await init_db()
    yield
    logger.info("Shutting down application...")
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Conversational Sales Intelligence & Autonomous WhatsApp Booking Agent API",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(webhook_router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Public health check endpoint."""
    return {"status": "healthy", "app": settings.APP_NAME}
