"""Unit tests for CRM adapter and payload synchronization."""

import pytest
from src.crm.airtable import AirtableCRMAdapter
from src.crm.base import CRMLeadPayload


@pytest.mark.asyncio
async def test_airtable_sync_lead_success():
    """Verify that AirtableCRMAdapter synchronizes a qualified lead and returns record ID."""
    adapter = AirtableCRMAdapter()
    payload = CRMLeadPayload(
        phone_number="+15559876543",
        contact_name="Elena Rostova",
        company_name="Vanguard Logistics",
        budget=15000.0,
        currency="USD",
        company_size="100-250",
        business_problem="Manual booking errors in WhatsApp channel",
        urgency="HIGH",
        decision_maker="YES",
        qualification_status="QUALIFIED",
        qualification_score=0.95,
        conversation_state="BOOKED",
        booking_status="CONFIRMED",
        calendar_event_id="gcal_test_event_999",
        meeting_url="https://meet.google.com/abc-defg-hij",
        consent_given=True,
        is_escalated=False,
        notes="High-intent prospect",
    )

    res = await adapter.sync_lead(payload)
    assert res["status"] == "SYNCED"
    assert res["external_record_id"].startswith("rec_")


@pytest.mark.asyncio
async def test_airtable_idempotent_update():
    """Verify that multiple sync calls for the same phone number update the same record."""
    adapter = AirtableCRMAdapter()
    phone = "+15551113333"

    payload1 = CRMLeadPayload(
        phone_number=phone,
        contact_name="Dave Miller",
        company_name="Miller Tech",
        budget=2000.0,
        currency="USD",
        company_size="10",
        business_problem="Lead capture",
        urgency="MEDIUM",
        decision_maker="YES",
        qualification_status="QUALIFIED",
        qualification_score=0.80,
        conversation_state="QUALIFIED",
        booking_status=None,
        calendar_event_id=None,
        meeting_url=None,
        consent_given=True,
        is_escalated=False,
        notes=None,
    )
    res1 = await adapter.sync_lead(payload1)
    rec_id1 = res1["external_record_id"]

    # Second sync after booking confirmed
    payload2 = CRMLeadPayload(
        phone_number=phone,
        contact_name="Dave Miller",
        company_name="Miller Tech",
        budget=2000.0,
        currency="USD",
        company_size="10",
        business_problem="Lead capture",
        urgency="MEDIUM",
        decision_maker="YES",
        qualification_status="QUALIFIED",
        qualification_score=0.80,
        conversation_state="BOOKED",
        booking_status="CONFIRMED",
        calendar_event_id="gcal_777",
        meeting_url="https://meet.google.com/test",
        consent_given=True,
        is_escalated=False,
        notes="Booked slot successfully",
    )
    res2 = await adapter.sync_lead(payload2)
    rec_id2 = res2["external_record_id"]

    assert rec_id1 == rec_id2  # Idempotent record persistence!
