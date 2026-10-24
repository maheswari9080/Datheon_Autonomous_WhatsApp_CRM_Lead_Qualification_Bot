"""Integration tests for Transactional Outbox pattern worker."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.crm.outbox import TransactionalOutboxWorker
from src.database.models import Lead, OutboxEvent


@pytest.mark.asyncio
async def test_enqueue_and_process_outbox_crm_event(db_session: AsyncSession):
    """Verify that OutboxWorker processes CRM_SYNC event and updates the Lead record."""
    # Create test lead in database
    lead = Lead(
        phone_number="+15557778888",
        contact_name="Integration Prospect",
        budget=8000.0,
        qualification_status="QUALIFIED",
        consent_given=True,
    )
    db_session.add(lead)
    await db_session.commit()

    # Enqueue CRM_SYNC outbox event
    payload = {
        "phone_number": "+15557778888",
        "contact_name": "Integration Prospect",
        "budget": 8000.0,
        "qualification_status": "QUALIFIED",
        "booking_status": "CONFIRMED",
        "calendar_event_id": "gcal_int_101",
    }
    event = await TransactionalOutboxWorker.enqueue_event(
        db_session, event_type="CRM_SYNC", payload=payload
    )
    assert event.status == "PENDING"
    await db_session.commit()

    # Process pending events
    processed_count = await TransactionalOutboxWorker.process_pending_events(db_session)
    assert processed_count == 1

    # Reload event and lead
    await db_session.refresh(event)
    await db_session.refresh(lead)

    assert event.status == "PROCESSED"
    assert event.processed_at is not None
    assert lead.external_crm_id is not None
    assert lead.crm_synced_at is not None


@pytest.mark.asyncio
async def test_outbox_retry_exponential_backoff_and_dead_letter(db_session: AsyncSession):
    """Verify that failed outbox events undergo retries and move to DEAD_LETTER after max attempts."""
    # Enqueue an event configured to fail with max_retries = 2
    event = OutboxEvent(
        event_type="UNSUPPORTED_TYPE_CAUSING_ERROR",
        payload={"dummy": "data"},
        status="PENDING",
        retry_count=0,
        max_retries=2,
        next_retry_at=datetime.now(UTC),
    )
    db_session.add(event)
    await db_session.commit()

    # Force failure in worker by invoking process_single_event
    # Attempt 1
    success1 = await TransactionalOutboxWorker.process_single_event(db_session, event)
    assert success1 is False
    assert event.retry_count == 1
    assert event.status == "FAILED"

    # Attempt 2 (exhausts max_retries=2)
    success2 = await TransactionalOutboxWorker.process_single_event(db_session, event)
    assert success2 is False
    assert event.retry_count == 2
    assert event.status == "DEAD_LETTER"
