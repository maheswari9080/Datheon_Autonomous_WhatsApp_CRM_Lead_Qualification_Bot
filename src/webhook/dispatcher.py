"""Webhook event dispatcher and stateful conversation orchestrator."""

from datetime import date, datetime, timezone
import re
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import get_llm_client
from src.ai.guardrails import InputGuardrails
from src.ai.qualification import policy_engine
from src.ai.schemas import ExtractedLeadData, QualificationStatusEnum
from src.calendar.base import TimeSlot
from src.calendar.scheduler import scheduler
from src.core.logging import correlation_id_ctx, get_logger
from src.crm.outbox import TransactionalOutboxWorker
from src.database.models import AuditEvent, BookingRecord, Conversation, Lead, Message
from src.database.session import async_session_factory
from src.escalation.controller import EscalationController
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


async def execute_conversation_turn(
    db: AsyncSession,
    conversation: Conversation,
    lead: Lead,
    inbound_text: str,
    correlation_id: str,
) -> None:
    """Execute AI extraction, deterministic qualification, booking, or escalation for inbound message."""
    # 1. Check if conversation is currently in HUMAN_HANDOFF
    if conversation.current_state == ConversationState.HUMAN_HANDOFF.value:
        logger.info(
            f"Conversation {conversation.id} is in HUMAN_HANDOFF; autonomous messaging suspended.",
            extra={"extra_fields": {"conversation_id": conversation.id}},
        )
        return

    # 2. STRIDE & Input Guardrails
    cleaned_text, is_malicious, violation_reason = InputGuardrails.inspect_and_sanitize(inbound_text)
    if is_malicious:
        await EscalationController.trigger_handoff(
            db=db,
            conversation=conversation,
            lead=lead,
            trigger_type="ADVERSARIAL_ATTACK",
            reason=violation_reason or "Adversarial input detected",
        )
        return

    # 3. Escalation Check: Explicit Human Request or Frustration
    should_esc, trigger_type, esc_reason = EscalationController.should_escalate(
        text=cleaned_text,
        consecutive_failures=conversation.state_metadata.get("consecutive_failures", 0),
    )
    if should_esc:
        await EscalationController.trigger_handoff(
            db=db,
            conversation=conversation,
            lead=lead,
            trigger_type=trigger_type,
            reason=esc_reason,
        )
        return

    # Fetch recent message history for context
    msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .limit(10)
    )
    history_records = (await db.execute(msg_stmt)).scalars().all()
    dialogue_history = [{"role": "user" if m.direction == "INBOUND" else "assistant", "content": m.content} for m in history_records]
    dialogue_history.append({"role": "user", "content": cleaned_text})

    # 4. AI Intelligence Extraction
    llm_client = get_llm_client()
    existing_lead_model = ExtractedLeadData(
        contact_name=lead.contact_name,
        company_name=lead.company_name,
        budget_amount=lead.budget,
        currency=lead.currency,
        company_size=lead.company_size,
        business_problem=lead.business_problem,
    )
    extraction = await llm_client.extract_lead_intelligence(dialogue_history, existing_lead_model)

    # Synchronize extracted fields to Lead model
    if extraction.lead.contact_name:
        lead.contact_name = extraction.lead.contact_name
    if extraction.lead.company_name:
        lead.company_name = extraction.lead.company_name
    if extraction.lead.budget_amount is not None:
        lead.budget = extraction.lead.budget_amount
    if extraction.lead.company_size:
        lead.company_size = extraction.lead.company_size
    if extraction.lead.business_problem:
        lead.business_problem = extraction.lead.business_problem
    lead.urgency = extraction.lead.urgency.value
    lead.decision_maker = extraction.lead.decision_maker.value

    # 5. Deterministic Backend Qualification Policy Evaluation
    qual_status, reason, score = policy_engine.evaluate_qualification(extraction)
    lead.qualification_status = qual_status.value
    lead.qualification_score = score

    # Check for sentiment escalation post-extraction
    if extraction.customer_sentiment_score <= -0.6:
        await EscalationController.trigger_handoff(
            db=db,
            conversation=conversation,
            lead=lead,
            trigger_type="NEGATIVE_SENTIMENT",
            reason=f"High negative sentiment detected: {extraction.customer_sentiment_score}",
            recent_dialogue=dialogue_history,
        )
        return

    # 6. Drive FSM and Response Generation
    if qual_status == QualificationStatusEnum.NOT_QUALIFIED:
        # FSM -> NOT_QUALIFIED -> CLOSED
        ConversationFSM.transition(
            conversation.current_state,
            ConversationState.NOT_QUALIFIED,
            conversation.state_metadata,
            reason=reason,
        )
        new_state, updated_meta = ConversationFSM.transition(
            ConversationState.NOT_QUALIFIED,
            ConversationState.CLOSED,
            conversation.state_metadata,
            reason="Graceful disqualification closure",
        )
        conversation.previous_state = conversation.current_state
        conversation.current_state = new_state.value
        conversation.state_metadata = updated_meta

        disqual_msg = (
            "Thank you for sharing your project details. At this stage, our enterprise automation "
            "platform requires a higher minimum budget scope. We appreciate your time and wish you the best!"
        )
        await TransactionalOutboxWorker.enqueue_event(
            db, "WHATSAPP_DISPATCH", {"recipient_phone": lead.phone_number, "message_body": disqual_msg}
        )

    elif qual_status == QualificationStatusEnum.NEEDS_MORE_INFORMATION:
        # FSM -> NEEDS_INFORMATION
        if ConversationFSM.is_legal_transition(conversation.current_state, ConversationState.NEEDS_INFORMATION):
            new_state, updated_meta = ConversationFSM.transition(
                conversation.current_state,
                ConversationState.NEEDS_INFORMATION,
                conversation.state_metadata,
                reason="Prompting for missing qualification fields",
            )
            conversation.previous_state = conversation.current_state
            conversation.current_state = new_state.value
            conversation.state_metadata = updated_meta

        followup = extraction.next_recommended_question or "Could you share a bit more about your budget and timeline?"
        await TransactionalOutboxWorker.enqueue_event(
            db, "WHATSAPP_DISPATCH", {"recipient_phone": lead.phone_number, "message_body": followup}
        )

    elif qual_status == QualificationStatusEnum.QUALIFIED:
        # Check if customer is confirming a slot or requesting slots
        offered_slots = conversation.state_metadata.get("offered_slots", [])
        is_slot_selection = bool(re.search(r"\b(slot|option|confirm|book|yes|1|2|3|tomorrow|tuesday|monday)\b", cleaned_text, re.IGNORECASE))

        if offered_slots and is_slot_selection:
            # Slot confirmed! FSM: QUALIFIED/BOOKING -> BOOKED
            slot_info = offered_slots[0]
            slot = TimeSlot(
                slot_id=slot_info["slot_id"],
                start_time=datetime.fromisoformat(slot_info["start_time"]),
                end_time=datetime.fromisoformat(slot_info["end_time"]),
                formatted_display=slot_info["formatted_display"],
            )

            # Confirm booking with Calendar Scheduler
            booking = await scheduler.confirm_booking(
                slot=slot,
                lead_name=lead.contact_name or "Valued Prospect",
                lead_phone=lead.phone_number,
                summary=f"Datheon Demo - {lead.company_name or lead.contact_name or 'Prospect'}",
            )

            # Create BookingRecord in DB
            booking_record = BookingRecord(
                conversation_id=conversation.id,
                lead_id=lead.id,
                provider=booking["provider"],
                external_event_id=booking["event_id"],
                start_time=slot.start_time,
                end_time=slot.end_time,
                status="CONFIRMED",
                meeting_url=booking.get("meeting_url"),
                metadata_json=booking,
            )
            db.add(booking_record)

            # FSM transition to BOOKED
            if ConversationFSM.is_legal_transition(conversation.current_state, ConversationState.BOOKING):
                new_state, updated_meta = ConversationFSM.transition(
                    conversation.current_state, ConversationState.BOOKING, conversation.state_metadata
                )
                conversation.current_state = new_state.value
            new_state, updated_meta = ConversationFSM.transition(
                conversation.current_state, ConversationState.BOOKED, conversation.state_metadata, reason="Booking confirmed"
            )
            conversation.previous_state = conversation.current_state
            conversation.current_state = new_state.value
            conversation.state_metadata = updated_meta

            # Enqueue CRM Synchronization Outbox Event
            crm_payload = {
                "phone_number": lead.phone_number,
                "contact_name": lead.contact_name,
                "company_name": lead.company_name,
                "budget": lead.budget,
                "qualification_status": lead.qualification_status,
                "booking_status": "CONFIRMED",
                "calendar_event_id": booking["event_id"],
                "meeting_url": booking.get("meeting_url"),
            }
            await TransactionalOutboxWorker.enqueue_event(db, "CRM_SYNC", crm_payload)

            # Enqueue WhatsApp Confirmation
            confirm_msg = (
                f"🎉 Excellent! Your demonstration has been confirmed for {slot.formatted_display}.\n"
                f"Join URL: {booking.get('meeting_url')}\n"
                f"We look forward to speaking with you!"
            )
            await TransactionalOutboxWorker.enqueue_event(
                db, "WHATSAPP_DISPATCH", {"recipient_phone": lead.phone_number, "message_body": confirm_msg}
            )

        else:
            # Transition to QUALIFIED and offer slots
            if ConversationFSM.is_legal_transition(conversation.current_state, ConversationState.QUALIFIED):
                new_state, updated_meta = ConversationFSM.transition(
                    conversation.current_state,
                    ConversationState.QUALIFIED,
                    conversation.state_metadata,
                    reason="Lead satisfied all B2B qualification criteria",
                )
                conversation.previous_state = conversation.current_state
                conversation.current_state = new_state.value
                conversation.state_metadata = updated_meta

            # Fetch available calendar slots
            slots = await scheduler.get_interactive_slots(start_date=date.today(), limit=3, user_phone=lead.phone_number)
            if slots:
                # Lock first slot provisionally
                scheduler.reserve_slot_lock(slots[0], user_phone=lead.phone_number)
                conversation.state_metadata["offered_slots"] = [
                    {
                        "slot_id": s.slot_id,
                        "start_time": s.start_time.isoformat(),
                        "end_time": s.end_time.isoformat(),
                        "formatted_display": s.formatted_display,
                    }
                    for s in slots
                ]

                slot_lines = "\n".join([f"• {s.formatted_display}" for s in slots])
                invitation_msg = (
                    f"Great news, {lead.contact_name or 'there'}! Based on your requirements, we would love to schedule a demonstration.\n\n"
                    f"Here are our earliest available slots:\n{slot_lines}\n\n"
                    f"Reply with 'Confirm' to lock in the first slot or let us know your preferred time!"
                )
                await TransactionalOutboxWorker.enqueue_event(
                    db, "WHATSAPP_DISPATCH", {"recipient_phone": lead.phone_number, "message_body": invitation_msg}
                )


async def process_inbound_webhook(payload: dict[str, Any], correlation_id: str) -> None:
    """Background processor for verified Meta WhatsApp webhook payloads."""
    correlation_id_ctx.set(correlation_id)
    messages, statuses = WhatsAppPayloadParser.parse_payload(payload)

    async with async_session_factory() as db:
        # 1. Process Status Callbacks (never alters lead qualification)
        for st in statuses:
            logger.info(
                f"WhatsApp Status Receipt: {st.status} for message {st.message_id}",
                extra={"extra_fields": {"message_id": st.message_id, "status": st.status}},
            )
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
            is_dup = await deduplicator.is_duplicate(msg.message_id, db)
            if is_dup:
                logger.warning(
                    f"Skipping duplicate webhook message: {msg.message_id}",
                    extra={"extra_fields": {"message_id": msg.message_id}},
                )
                continue

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
            deduplicator.mark_processed_in_memory(msg.message_id)

            audit = AuditEvent(
                correlation_id=correlation_id,
                event_type="INBOUND_MESSAGE_RECEIVED",
                actor="CUSTOMER",
                resource_id=conversation.id,
                details={"message_id": msg.message_id, "text": msg.text_content},
            )
            db.add(audit)

            # Advance FSM if NEW
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

            # Execute conversational intelligence turn
            await execute_conversation_turn(
                db=db,
                conversation=conversation,
                lead=lead,
                inbound_text=msg.text_content,
                correlation_id=correlation_id,
            )

        await db.commit()
