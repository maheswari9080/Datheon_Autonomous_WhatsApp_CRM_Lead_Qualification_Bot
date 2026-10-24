"""Unit tests for calendar adapters, slot availability, and conflict locking."""

from datetime import date, datetime, timedelta, timezone
import pytest
from src.calendar.calcom import CalComCalendarAdapter
from src.calendar.google import GoogleCalendarAdapter
from src.calendar.scheduler import BookingScheduler
from src.core.exceptions import CalendarSlotUnavailableError


@pytest.mark.asyncio
async def test_google_calendar_slots_generation():
    """Verify that GoogleCalendarAdapter returns valid weekday slots adhering to business hours."""
    adapter = GoogleCalendarAdapter(business_start=10, business_end=12, slot_duration=30, buffer_minutes=0, min_notice_hours=0)
    # Find next Monday
    today = date.today()
    next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)

    slots = await adapter.get_available_slots(start_date=next_monday, days=1)
    # Between 10:00 and 12:00 with 30m slots -> 10:00, 10:30, 11:00, 11:30 (4 slots)
    assert len(slots) == 4
    assert slots[0].start_time.hour == 10
    assert slots[-1].end_time.hour == 12


@pytest.mark.asyncio
async def test_calcom_adapter_booking_and_cancellation():
    """Verify CalComCalendarAdapter creates confirmed booking and cancels cleanly."""
    adapter = CalComCalendarAdapter()
    start_time = datetime.now(timezone.utc) + timedelta(days=2, hours=3)
    end_time = start_time + timedelta(minutes=30)

    booking = await adapter.create_booking(
        lead_name="Marcus Vance",
        lead_phone="+15554443322",
        start_time=start_time,
        end_time=end_time,
        summary="Automated Demo",
    )

    assert booking["status"] == "CONFIRMED"
    assert "cal.com/booking/" in booking["meeting_url"]
    assert booking["event_id"].startswith("cal_")

    # Cancel
    cancelled = await adapter.cancel_booking(booking["event_id"])
    assert cancelled is True


@pytest.mark.asyncio
async def test_scheduler_slot_locking_prevents_race_condition():
    """Verify that BookingScheduler locks slots, preventing concurrent collisions."""
    scheduler = BookingScheduler(adapter=GoogleCalendarAdapter())
    start = datetime.now(timezone.utc) + timedelta(days=2, hours=4)
    end = start + timedelta(minutes=30)

    from src.calendar.base import TimeSlot
    slot = TimeSlot(
        slot_id="slot_race_test_101",
        start_time=start,
        end_time=end,
        formatted_display="Wed, Oct 28 at 02:00 PM UTC",
    )

    # User A locks slot
    assert scheduler.reserve_slot_lock(slot, user_phone="+1111111111") is True

    # User B attempts to reserve the same slot -> False (rejected)
    assert scheduler.reserve_slot_lock(slot, user_phone="+2222222222") is False

    # User B attempts to confirm without holding lock -> raises error
    with pytest.raises(CalendarSlotUnavailableError):
        await scheduler.confirm_booking(slot, lead_name="User B", lead_phone="+2222222222")

    # User A confirms booking -> succeeds
    booking = await scheduler.confirm_booking(slot, lead_name="User A", lead_phone="+1111111111")
    assert booking["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_double_booking_prevention():
    """Verify that adapter rejects booking if slot time overlaps with an existing appointment."""
    adapter = GoogleCalendarAdapter()
    t1 = datetime.now(timezone.utc) + timedelta(days=1, hours=2)
    t2 = t1 + timedelta(minutes=30)

    await adapter.create_booking("Lead One", "+15551112222", t1, t2, "Demo 1")

    # Attempt to book overlapping time
    with pytest.raises(CalendarSlotUnavailableError):
        await adapter.create_booking("Lead Two", "+15553334444", t1, t2, "Demo 2")
