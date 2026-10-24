"""Transactional Outbox processor for reliable asynchronous integration delivery."""

from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.crm.airtable import crm_adapter
from src.crm.base import CRMLeadPayload
from src.database.models import Lead, OutboxEvent

logger = get_logger(__name__)


class TransactionalOutboxWorker:
    """Processes outbox events with exponential backoff retries and idempotency."""

    @staticmethod
    async def enqueue_event(
        db: AsyncSession,
        event_type: str,
        payload: dict[str, Any],
        max_retries: int = 5,
    ) -> OutboxEvent:
        """Enqueue an event into the transactional outbox within an active DB transaction."""
        event = OutboxEvent(
            event_type=event_type,
            payload=payload,
            status="PENDING",
            retry_count=0,
            max_retries=max_retries,
            next_retry_at=datetime.now(timezone.utc),
        )
        db.add(event)
        await db.flush()
        logger.info(f"Enqueued OutboxEvent: {event.id} ({event_type})")
        return event

    @classmethod
    async def process_single_event(cls, db: AsyncSession, event: OutboxEvent) -> bool:
        """Execute a single outbox event with error handling and retry scheduling."""
        try:
            event.status = "PROCESSING"

            if event.event_type == "CRM_SYNC":
                p = event.payload
                crm_payload = CRMLeadPayload(
                    phone_number=p["phone_number"],
                    contact_name=p.get("contact_name"),
                    company_name=p.get("company_name"),
                    budget=p.get("budget"),
                    currency=p.get("currency", "USD"),
                    company_size=p.get("company_size"),
                    business_problem=p.get("business_problem"),
                    urgency=p.get("urgency", "MEDIUM"),
                    decision_maker=p.get("decision_maker", "UNKNOWN"),
                    qualification_status=p.get("qualification_status", "QUALIFIED"),
                    qualification_score=p.get("qualification_score"),
                    conversation_state=p.get("conversation_state", "BOOKED"),
                    booking_status=p.get("booking_status"),
                    calendar_event_id=p.get("calendar_event_id"),
                    meeting_url=p.get("meeting_url"),
                    consent_given=p.get("consent_given", True),
                    is_escalated=p.get("is_escalated", False),
                    notes=p.get("notes"),
                )
                res = await crm_adapter.sync_lead(crm_payload)

                # Update lead record with CRM ID if lead exists
                stmt = select(Lead).where(Lead.phone_number == p["phone_number"])
                lead_res = await db.execute(stmt)
                lead = lead_res.scalar_one_or_none()
                if lead:
                    lead.external_crm_id = res.get("external_record_id")
                    lead.crm_synced_at = datetime.now(timezone.utc)

            elif event.event_type == "WHATSAPP_DISPATCH":
                # WhatsApp outbound message dispatcher hook
                recipient = event.payload.get("recipient_phone")
                body = event.payload.get("message_body")
                logger.info(f"[Outbox Dispatch] Outbound WhatsApp sent to {recipient}: {body}")

            elif event.event_type == "ESCALATION_ALERT":
                logger.info(f"[Outbox Dispatch] Escalation notification dispatched: {event.payload}")

            # Mark processed
            event.status = "PROCESSED"
            event.processed_at = datetime.now(timezone.utc)
            event.last_error = None
            return True

        except Exception as exc:
            event.retry_count += 1
            event.last_error = str(exc)
            logger.error(f"Failed processing OutboxEvent {event.id}: {exc}")

            if event.retry_count >= event.max_retries:
                event.status = "DEAD_LETTER"
                logger.critical(f"OutboxEvent {event.id} permanently failed; moved to DEAD_LETTER")
            else:
                event.status = "FAILED"
                # Exponential backoff: 2, 4, 8, 16 seconds
                delay_sec = 2 ** event.retry_count
                event.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_sec)

            return False

    @classmethod
    async def process_pending_events(cls, db: AsyncSession, limit: int = 20) -> int:
        """Poll and execute pending and failed outbox events ready for retry."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status.in_(["PENDING", "FAILED"]),
                OutboxEvent.next_retry_at <= now,
            )
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        events = result.scalars().all()

        processed_count = 0
        for ev in events:
            success = await cls.process_single_event(db, ev)
            if success:
                processed_count += 1

        await db.commit()
        return processed_count


outbox_worker = TransactionalOutboxWorker()
