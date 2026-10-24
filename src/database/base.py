"""SQLAlchemy 2.0 declarative base and common mixins."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy 2.0 ORM models."""

    pass


class TimestampMixin:
    """Provides automatic created_at and updated_at UTC timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """Provides a UUID string primary key."""

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
