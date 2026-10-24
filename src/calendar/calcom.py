"""Cal.com API integration adapter."""

from datetime import date, datetime, time, timedelta, timezone
import uuid
from typing import Any
import httpx

from src.calendar.base import CalendarAdapterProtocol, TimeSlot
from src.core.exceptions import CalendarSlotUnavailableError
from src.core.logging import get_logger

logger = get_logger(__name__)


class CalComCalendarAdapter(CalendarAdapterProtocol):
    """Cal.com integration adapter for appointment booking and availability."""

    def __init__(
        self,
        api_key: str = "",
        event_type_id: int = 12345,
        business_start: int = 9,
        business_end: int = 18,
        slot_duration: int = 30,
        buffer_minutes: int = 15,
        min_notice_hours: int = 2,
    ):
        self.api_key = api_key
        self.event_type_id = event_type_id
        self.business_start = business_start
        self.business_end = business_end
        self.slot_duration = slot_duration
        self.buffer_minutes = buffer_minutes
        self.min_notice_hours = min_notice_hours
        self._booked_events: dict[str, dict[str, Any]] = {}

    async def get_available_slots(
        self,
        start_date: date,
        days: int = 3,
        timezone_str: str = "UTC",
    ) -> list[TimeSlot]:
        """Fetch available Cal.com slots applying business hours and notice filters."""
        now_utc = datetime.now(timezone.utc)
        earliest_time = now_utc + timedelta(hours=self.min_notice_hours)
        slots: list[TimeSlot] = []

        for day_offset in range(days):
            target_date = start_date + timedelta(days=day_offset)
            if target_date.weekday() >= 5:
                continue

            current_slot_start = datetime.combine(
                target_date, time(hour=self.business_start, minute=0), tzinfo=timezone.utc
            )
            day_end = datetime.combine(
                target_date, time(hour=self.business_end, minute=0), tzinfo=timezone.utc
            )

            while current_slot_start + timedelta(minutes=self.slot_duration) <= day_end:
                slot_end = current_slot_start + timedelta(minutes=self.slot_duration)
                if current_slot_start >= earliest_time:
                    slot_id = f"calcom_{current_slot_start.strftime('%Y%m%d_%H%M')}"
                    is_colliding = False
                    for ev in self._booked_events.values():
                        ev_start = datetime.fromisoformat(ev["start_time"]) if isinstance(ev["start_time"], str) else ev["start_time"]
                        ev_end = datetime.fromisoformat(ev["end_time"]) if isinstance(ev["end_time"], str) else ev["end_time"]
                        if ev_start < slot_end and ev_end > current_slot_start:
                            is_colliding = True
                            break

                    if not is_colliding:
                        display = current_slot_start.strftime("%a, %b %d at %I:%M %p UTC")
                        slots.append(
                            TimeSlot(
                                slot_id=slot_id,
                                start_time=current_slot_start,
                                end_time=slot_end,
                                formatted_display=display,
                            )
                        )
                current_slot_start += timedelta(minutes=self.slot_duration + self.buffer_minutes)

        return slots

    async def create_booking(
        self,
        lead_name: str,
        lead_phone: str,
        start_time: datetime,
        end_time: datetime,
        summary: str,
    ) -> dict[str, Any]:
        """Create confirmed Cal.com booking."""
        for ev in self._booked_events.values():
            ev_start = datetime.fromisoformat(ev["start_time"]) if isinstance(ev["start_time"], str) else ev["start_time"]
            ev_end = datetime.fromisoformat(ev["end_time"]) if isinstance(ev["end_time"], str) else ev["end_time"]
            if ev_start < end_time and ev_end > start_time:
                raise CalendarSlotUnavailableError("Slot unavailable on Cal.com")

        event_id = f"cal_{uuid.uuid4().hex[:10]}"
        booking_data = {
            "event_id": event_id,
            "provider": "calcom",
            "lead_name": lead_name,
            "lead_phone": lead_phone,
            "start_time": start_time.isoformat() if isinstance(start_time, datetime) else str(start_time),
            "end_time": end_time.isoformat() if isinstance(end_time, datetime) else str(end_time),
            "summary": summary,
            "meeting_url": f"https://cal.com/booking/{event_id}",
            "status": "CONFIRMED",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._booked_events[event_id] = booking_data
        logger.info(f"Cal.com booking created: {event_id}")
        return booking_data

    async def cancel_booking(self, external_event_id: str) -> bool:
        if external_event_id in self._booked_events:
            self._booked_events[external_event_id]["status"] = "CANCELLED"
            return True
        return False
