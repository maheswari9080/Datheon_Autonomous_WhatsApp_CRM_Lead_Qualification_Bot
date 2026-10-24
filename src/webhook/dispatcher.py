"""Webhook event dispatcher and stateful conversation orchestrator."""

from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import correlation_id_ctx, get_logger
from src.database.models import AuditEvent, Conversation, Lead, Message
from src.database.session import async_session_factory
from src.fsm.machine import ConversationFSM
from src.fsm.states import ConversationState
from src.webhook.deduplicator import deduplicator
from src.webhook.parser import WhatsAppPayloadParser

logger = get_logger(__name__)


async def get_or_create_lead(
    db: AsyncSession,
    phone_number: str,
    contact_name: str | None = None,
) -> Lead:
    """Retrieve existing lead or create new lead by phone number."""
    stmt = select(Lead).where(Lead.phone_number == phone_number)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        lead = Lead(
            phone_number=phone_number,
            contact_name=contact_name,
            qualification_status="NEW",
            consent_given=True,
        )
        db.add(lead)
        await db.flush()
        logger.info(f"Created new lead for phone {phone_number}", extra={"extra_fields": {"lead_id": lead.id}})
    elif contact_name and not lead.contact_name:
        lead.contact_name = contact_name
        await db.flush()

    return lead


async def get_or_create_conversation(db: AsyncSession, lead: Lead) -> Conversation:
    """Retrieve active conversation or create a new one."""
    stmt = (
        select(Conversation)
        .where(Conversation.lead_id == lead.id, Conversation.is_active == True)  # noqa: E712
        .order_by(Conversation.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            lead_id=lead.id,
            phone_number=lead.phone_number,
            current_state=ConversationState.NEW.value,
            state_metadata={"created_via": "whatsapp_webhook"},
            is_active=True,
        )
        db.add(conversation)
        await db.flush()
        logger.info(
            f"Created new conversation for lead {lead.id}",
            extra={"extra_fields": {"conversation_id": conversation.id}},
        )

    return conversation


async def process_inbound_webhook(payload: dict[str, Any], correlation_id: str) -> None:
    """Background processor for verified Meta WhatsApp webhook payloads."""
    correlation_id_ctx.set(correlation_id)
    messages, statuses = WhatsAppPayloadParser.parse_payload(payload)

    async with async_session_factory() as db:
        # 1. Process Status Callbacks (purely operational; never alters lead qualification)
        for st in statuses:
            logger.info(
                f"WhatsApp Status Receipt: {st.status} for message {st.message_id}",
                extra={"extra_fields": {"message_id": st.message_id, "status": st.status}},
            )
            # Record audit event for message delivery tracking
            audit = AuditEvent(
                correlation_id=correlation_id,
                event_type="MESSAGE_STATUS_RECEIPT",
                actor="SYSTEM",
                resource_id=st.message_id,
                details={"recipient": st.recipient_phone, "status": st.status, "error": st.error_details},
            )
            db.add(audit)

        # 2. Process Inbound Customer Messages
        for msg in messages:
            # Idempotency / Deduplication check
            is_dup = await deduplicator.is_duplicate(msg.message_id, db)
            if is_dup:
                logger.warning(
                    f"Skipping duplicate webhook message: {msg.message_id}",
                    extra={"extra_fields": {"message_id": msg.message_id}},
                )
                continue

            # Recover state
            lead = await get_or_create_lead(db, msg.sender_phone, msg.contact_name)
            conversation = await get_or_create_conversation(db, lead)

            # Persist inbound message
            db_msg = Message(
                conversation_id=conversation.id,
                meta_message_id=msg.message_id,
                direction="INBOUND",
                sender_id=msg.sender_phone,
                message_type=msg.message_type,
                content=msg.text_content,
                payload_json=msg.raw_payload,
            )
            db.add(db_msg)

            # Mark processed in deduplication cache
            deduplicator.mark_processed_in_memory(msg.message_id)

            # Audit event
            audit = AuditEvent(
                correlation_id=correlation_id,
                event_type="INBOUND_MESSAGE_RECEIVED",
                actor="CUSTOMER",
                resource_id=conversation.id,
                details={"message_id": msg.message_id, "text": msg.text_content},
            )
            db.add(audit)

            # Advance FSM if conversation is in NEW state
            if conversation.current_state == ConversationState.NEW.value:
                new_state, updated_meta = ConversationFSM.transition(
                    conversation.current_state,
                    ConversationState.GREETING,
                    conversation.state_metadata,
                    reason="First customer message received",
                )
                conversation.previous_state = conversation.current_state
                conversation.current_state = new_state.value
                conversation.state_metadata = updated_meta

        await db.commit()
