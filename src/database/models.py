"""Core database relational models: Lead, Conversation, Message, and AuditEvent."""

from datetime import datetime, timezone
from typing import Any
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Lead(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stores business prospect profile and qualification attributes."""

    __tablename__ = "leads"

    phone_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    company_size: Mapped[str | None] = mapped_column(String(64), nullable=True)
    business_problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    urgency: Mapped[str] = mapped_column(String(16), default="MEDIUM", nullable=False)
    decision_maker: Mapped[str] = mapped_column(String(16), default="UNKNOWN", nullable=False)
    purchase_timeline: Mapped[str | None] = mapped_column(String(64), nullable=True)
    qualification_status: Mapped[str] = mapped_column(String(32), default="NEW", nullable=False)
    qualification_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    consent_given: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    external_crm_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    crm_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="lead", cascade="all, delete-orphan"
    )


class Conversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks stateful dialogue session with a prospect."""

    __tablename__ = "conversations"

    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    current_state: Mapped[str] = mapped_column(String(32), default="NEW", nullable=False, index=True)
    previous_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    state_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    lead: Mapped["Lead"] = relationship("Lead", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )
    bookings: Mapped[list["BookingRecord"]] = relationship(
        "BookingRecord", back_populates="conversation", cascade="all, delete-orphan"
    )
    escalations: Mapped[list["HandoffEscalation"]] = relationship(
        "HandoffEscalation", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base, UUIDPrimaryKeyMixin):
    """Individual inbound or outbound WhatsApp communication log."""

    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meta_message_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # INBOUND | OUTBOUND
    sender_id: Mapped[str] = mapped_column(String(64), nullable=False)   # Phone number or BOT
    message_type: Mapped[str] = mapped_column(String(32), default="TEXT", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    """Immutable audit log for security, repudiation defense, and state tracking."""

    __tablename__ = "audit_events"

    correlation_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    actor: Mapped[str] = mapped_column(String(32), nullable=False)  # CUSTOMER | BOT | SYSTEM | AGENT
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )


# Forward reference declarations to resolve in Commit 06
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.database.models_extended import BookingRecord, HandoffEscalation
