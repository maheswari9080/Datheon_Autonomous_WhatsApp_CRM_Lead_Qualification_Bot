"""E2E Test: Human Escalation, Autonomous Action Cease, and Operator Takeover."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.core.config import get_settings
from src.database.models import Conversation, HandoffEscalation, Lead, OutboxEvent
from src.database.session import async_session_factory
from src.fsm.states import ConversationState
from src.webhook.dispatcher import process_inbound_webhook
from tests.e2e.test_full_lead_journey import build_meta_webhook

settings = get_settings()


@pytest.mark.asyncio
async def test_human_escalation_and_operator_resolution(async_client: AsyncClient):
    """Verify explicit escalation suspends autonomous messaging until operator resolves."""
    phone = "15559990000"
    name = "Robert Taylor"

    # Step 1: Customer asks for human immediately
    payload = build_meta_webhook(
        phone=phone,
        name=name,
        text="I don't want a bot. Please connect me to a human representative right now.",
        msg_id="wamid.ESC_01",
    )
    await process_inbound_webhook(payload, "corr-esc-01")

    async with async_session_factory() as db:
        lead_stmt = select(Lead).where(Lead.phone_number == phone)
        lead = (await db.execute(lead_stmt)).scalar_one()

        conv_stmt = select(Conversation).where(Conversation.lead_id == lead.id)
        conv = (await db.execute(conv_stmt)).scalar_one()

        # FSM state must be HUMAN_HANDOFF
        assert conv.current_state == ConversationState.HUMAN_HANDOFF.value

        # HandoffEscalation record must exist
        esc_stmt = select(HandoffEscalation).where(HandoffEscalation.conversation_id == conv.id)
        esc = (await db.execute(esc_stmt)).scalar_one()
        assert esc.status == "OPEN"
        assert esc.trigger_type == "EXPLICIT_REQUEST"

        escalation_id = esc.id

    # Step 2: Customer sends another message while in HUMAN_HANDOFF
    # Autonomous sales messaging must NOT occur
    payload_2 = build_meta_webhook(
        phone=phone,
        name=name,
        text="Are you there? I have $50,000 budget.",
        msg_id="wamid.ESC_02",
    )
    await process_inbound_webhook(payload_2, "corr-esc-02")

    async with async_session_factory() as db:
        conv = (await db.execute(conv_stmt)).scalar_one()
        # Must stay in HUMAN_HANDOFF, not jump to QUALIFIED
        assert conv.current_state == ConversationState.HUMAN_HANDOFF.value

    # Step 3: Admin operator resolves ticket via REST API
    headers = {"X-Admin-API-Key": settings.ADMIN_API_KEY}
    resolve_body = {
        "assigned_agent": "Agent Smith",
        "resolution_notes": "Spoke with client on phone, enterprise demo arranged.",
        "resume_automation": True,
    }
    response = await async_client.post(
        f"/admin/escalations/{escalation_id}/resolve",
        headers=headers,
        json=resolve_body,
    )
    assert response.status_code == 200

    # Step 4: Verify escalation marked RESOLVED and state resumed
    async with async_session_factory() as db:
        esc = (await db.execute(esc_stmt)).scalar_one()
        assert esc.status == "RESOLVED"
        assert esc.assigned_agent == "Agent Smith"

        conv = (await db.execute(conv_stmt)).scalar_one()
        assert conv.current_state == ConversationState.DISCOVERY.value
