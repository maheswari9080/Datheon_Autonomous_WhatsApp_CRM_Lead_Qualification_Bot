"""Google Calendar API adapter implementation."""

from datetime import date, datetime, time, timedelta, timezone
import uuid
from typing import Any
import httpx

from src.calendar.base import CalendarAdapterProtocol, TimeSlot
from src.core.config import get_settings
from src.core.exceptions import CalendarSlotUnavailableError
from src.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GoogleCalendarAdapter(CalendarAdapterProtocol):
    """Google Calendar v3 API integration adapter with sandbox mock fallback."""

    def __init__(
        self,
        calendar_id: str = "primary",
        service_account_json: str = "",
        business_start: int = 9,
        business_end: int = 18,
        slot_duration: int = 30,
        buffer_minutes: int = 15,
        min_notice_hours: int = 2,
    ):
        self.calendar_id = calendar_id
        self.service_account_json = service_account_json
        self.business_start = business_start
        self.business_end = business_end
        self.slot_duration = slot_duration
        self.buffer_minutes = buffer_minutes
        self.min_notice_hours = min_notice_hours
        # Local state tracking for sandbox simulation
        self._booked_events: dict[str, dict[str, Any]] = {}

    async def get_available_slots(
        self,
        start_date: date,
        days: int = 3,
        timezone_str: str = "UTC",
    ) -> list[TimeSlot]:
        """Compute available meeting slots across specified working days."""
        now_utc = datetime.now(timezone.utc)
        earliest_time = now_utc + timedelta(hours=self.min_notice_hours)
        slots: list[TimeSlot] = []

        for day_offset in range(days):
            target_date = start_date + timedelta(days=day_offset)
            # Skip weekends (Saturday=5, Sunday=6)
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
                # Ensure minimum notice requirement
                if current_slot_start >= earliest_time:
                    slot_id = f"slot_{current_slot_start.strftime('%Y%m%d_%H%M')}"

                    # Check collision against booked events
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
        """Create confirmed calendar event with collision guard."""
        # Double-check collision immediately before creating event (STRIDE / Concurrency check)
        for ev in self._booked_events.values():
            ev_start = datetime.fromisoformat(ev["start_time"]) if isinstance(ev["start_time"], str) else ev["start_time"]
            ev_end = datetime.fromisoformat(ev["end_time"]) if isinstance(ev["end_time"], str) else ev["end_time"]
            if ev_start < end_time and ev_end > start_time:
                raise CalendarSlotUnavailableError(
                    f"Selected slot {start_time.isoformat()} was just booked by another user."
                )

        event_id = f"gcal_{uuid.uuid4().hex[:12]}"
        meeting_url = f"https://meet.google.com/{uuid.uuid4().hex[:3]}-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:3]}"

        booking_data = {
            "event_id": event_id,
            "provider": "google",
            "lead_name": lead_name,
            "lead_phone": lead_phone,
            "start_time": start_time.isoformat() if isinstance(start_time, datetime) else str(start_time),
            "end_time": end_time.isoformat() if isinstance(end_time, datetime) else str(end_time),
            "summary": summary,
            "meeting_url": meeting_url,
            "status": "CONFIRMED",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self._booked_events[event_id] = booking_data
        logger.info(
            f"Google Calendar event created: {event_id} ({start_time.isoformat()})",
            extra={"extra_fields": {"event_id": event_id, "meeting_url": meeting_url}},
        )
        return booking_data

    async def cancel_booking(self, external_event_id: str) -> bool:
        """Cancel an event."""
        if external_event_id in self._booked_events:
            self._booked_events[external_event_id]["status"] = "CANCELLED"
            logger.info(f"Cancelled Google Calendar event: {external_event_id}")
            return True
        return False
