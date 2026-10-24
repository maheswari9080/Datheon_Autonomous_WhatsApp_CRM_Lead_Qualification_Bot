"""E2E Test: Full Lead Qualification, Calendar Booking, and CRM Synchronization Journey."""

import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.security import compute_whatsapp_signature
from src.crm.outbox import TransactionalOutboxWorker
from src.database.models import BookingRecord, Conversation, Lead, OutboxEvent
from src.database.session import async_session_factory
from src.fsm.states import ConversationState
from src.webhook.dispatcher import process_inbound_webhook

settings = get_settings()


def build_meta_webhook(phone: str, name: str, text: str, msg_id: str) -> dict:
    """Helper formatting valid Meta WhatsApp JSON payloads."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "BIZ_12345",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "10001"},
                            "contacts": [{"profile": {"name": name}, "wa_id": phone}],
                            "messages": [
                                {
                                    "from": phone,
                                    "id": msg_id,
                                    "timestamp": "1710000000",
                                    "text": {"body": text},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_complete_autonomous_booking_journey(async_client: AsyncClient):
    """Scenario: New customer -> missing budget -> provides budget & qualifies -> selects slot -> booked & synced."""
    phone = "15550001111"
    name = "Samantha Wright"

    # Step 1: Initial Discovery Inquiry (missing budget)
    payload_1 = build_meta_webhook(
        phone=phone,
        name=name,
        text="Hi, I am from Apex Retail. We need to automate our WhatsApp customer support.",
        msg_id="wamid.MSG_E2E_01",
    )
    await process_inbound_webhook(payload_1, "corr-01")

    async with async_session_factory() as db:
        lead_stmt = select(Lead).where(Lead.phone_number == phone)
        lead = (await db.execute(lead_stmt)).scalar_one()
        assert lead.contact_name == name
        assert lead.qualification_status == "NEEDS_MORE_INFORMATION"

        conv_stmt = select(Conversation).where(Conversation.lead_id == lead.id)
        conv = (await db.execute(conv_stmt)).scalar_one()
        assert conv.current_state == ConversationState.NEEDS_INFORMATION.value

        # Check that follow-up question was dispatched
        outbox_stmt = select(OutboxEvent).where(OutboxEvent.event_type == "WHATSAPP_DISPATCH")
        dispatches = (await db.execute(outbox_stmt)).scalars().all()
        assert len(dispatches) >= 1
        assert "budget" in dispatches[-1].payload["message_body"].lower()

    # Step 2: Customer provides budget & decision maker status -> QUALIFIED
    payload_2 = build_meta_webhook(
        phone=phone,
        name=name,
        text="We have 80 staff members and an allocated budget of $8,000 USD. I am the VP of Operations.",
        msg_id="wamid.MSG_E2E_02",
    )
    await process_inbound_webhook(payload_2, "corr-02")

    async with async_session_factory() as db:
        lead = (await db.execute(lead_stmt)).scalar_one()
        assert lead.budget == 8000.0
        assert lead.qualification_status == "QUALIFIED"

        conv = (await db.execute(conv_stmt)).scalar_one()
        assert conv.current_state == ConversationState.QUALIFIED.value
        assert "offered_slots" in conv.state_metadata
        assert len(conv.state_metadata["offered_slots"]) > 0

    # Step 3: Customer confirms slot -> BOOKED
    payload_3 = build_meta_webhook(
        phone=phone,
        name=name,
        text="Yes please! Confirm slot 1 for me.",
        msg_id="wamid.MSG_E2E_03",
    )
    await process_inbound_webhook(payload_3, "corr-03")

    async with async_session_factory() as db:
        conv = (await db.execute(conv_stmt)).scalar_one()
        assert conv.current_state == ConversationState.BOOKED.value

        # Verify BookingRecord was created
        bk_stmt = select(BookingRecord).where(BookingRecord.lead_id == lead.id)
        booking = (await db.execute(bk_stmt)).scalar_one()
        assert booking.status == "CONFIRMED"
        assert booking.meeting_url is not None

        # Verify CRM sync event was enqueued
        crm_event_stmt = select(OutboxEvent).where(OutboxEvent.event_type == "CRM_SYNC")
        crm_event = (await db.execute(crm_event_stmt)).scalar_one()
        assert crm_event.status == "PENDING"

        # Execute Transactional Outbox Worker
        processed = await TransactionalOutboxWorker.process_pending_events(db)
        assert processed >= 1

        # Verify Lead record was stamped with external CRM ID
        lead_refreshed = (await db.execute(lead_stmt)).scalar_one()
        assert lead_refreshed.external_crm_id is not None
        assert lead_refreshed.crm_synced_at is not None
