"""Booking coordinator, slot locking, and conflict resolution engine."""

import time
from datetime import date
from typing import Any

from src.calendar.base import CalendarAdapterProtocol, TimeSlot
from src.calendar.calcom import CalComCalendarAdapter
from src.calendar.google import GoogleCalendarAdapter
from src.core.config import get_settings
from src.core.exceptions import CalendarSlotUnavailableError
from src.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class BookingScheduler:
    """Coordinates calendar slots, prevents double bookings with temporary locks, and resolves conflicts."""

    def __init__(
        self, adapter: CalendarAdapterProtocol | None = None, lock_timeout_seconds: int = 300
    ):
        self.lock_timeout_seconds = lock_timeout_seconds
        # Temporary slot reservations: slot_id -> {"phone": str, "locked_at": float, "slot": TimeSlot}
        self._slot_locks: dict[str, dict[str, Any]] = {}

        if adapter:
            self.adapter = adapter
        elif settings.CALENDAR_PROVIDER == "calcom":
            self.adapter = CalComCalendarAdapter(
                api_key=settings.CALCOM_API_KEY,
                event_type_id=settings.CALCOM_EVENT_TYPE_ID,
                business_start=settings.BUSINESS_HOURS_START,
                business_end=settings.BUSINESS_HOURS_END,
                slot_duration=settings.MEETING_DURATION_MINUTES,
                min_notice_hours=settings.MIN_NOTICE_HOURS,
            )
        else:
            self.adapter = GoogleCalendarAdapter(
                calendar_id=settings.GOOGLE_CALENDAR_ID,
                service_account_json=settings.GOOGLE_SERVICE_ACCOUNT_JSON,
                business_start=settings.BUSINESS_HOURS_START,
                business_end=settings.BUSINESS_HOURS_END,
                slot_duration=settings.MEETING_DURATION_MINUTES,
                min_notice_hours=settings.MIN_NOTICE_HOURS,
            )

    def _cleanup_expired_locks(self) -> None:
        """Release slot locks that exceeded lock_timeout_seconds."""
        now = time.time()
        expired = [
            k
            for k, v in self._slot_locks.items()
            if now - v["locked_at"] > self.lock_timeout_seconds
        ]
        for k in expired:
            logger.info(f"Released expired lock on slot: {k}")
            self._slot_locks.pop(k, None)

    async def get_interactive_slots(
        self,
        start_date: date,
        limit: int = 3,
        user_phone: str = "",
    ) -> list[TimeSlot]:
        """Fetch available slots, excluding slots locked by other users."""
        self._cleanup_expired_locks()
        all_slots = await self.adapter.get_available_slots(start_date=start_date, days=3)

        available: list[TimeSlot] = []
        for slot in all_slots:
            lock = self._slot_locks.get(slot.slot_id)
            if lock and lock["phone"] != user_phone:
                continue  # Locked by another user
            available.append(slot)
            if len(available) >= limit:
                break

        return available

    def reserve_slot_lock(self, slot: TimeSlot, user_phone: str) -> bool:
        """Place temporary reservation lock on slot during customer confirmation."""
        self._cleanup_expired_locks()
        existing = self._slot_locks.get(slot.slot_id)
        if existing and existing["phone"] != user_phone:
            logger.warning(f"Lock collision on slot {slot.slot_id} by user {user_phone}")
            return False

        self._slot_locks[slot.slot_id] = {
            "phone": user_phone,
            "locked_at": time.time(),
            "slot": slot,
        }
        logger.info(f"Slot {slot.slot_id} reserved for {user_phone}")
        return True

    def release_slot_lock(self, slot_id: str) -> None:
        """Release temporary lock."""
        self._slot_locks.pop(slot_id, None)

    async def confirm_booking(
        self,
        slot: TimeSlot,
        lead_name: str,
        lead_phone: str,
        summary: str = "Datheon Product Demonstration",
    ) -> dict[str, Any]:
        """Verify lock and execute confirmed booking via calendar adapter."""
        self._cleanup_expired_locks()
        lock = self._slot_locks.get(slot.slot_id)
        if lock and lock["phone"] != lead_phone:
            raise CalendarSlotUnavailableError(
                f"Slot {slot.formatted_display} is no longer reserved for this user."
            )

        try:
            booking = await self.adapter.create_booking(
                lead_name=lead_name,
                lead_phone=lead_phone,
                start_time=slot.start_time,
                end_time=slot.end_time,
                summary=summary,
            )
            # Remove lock upon confirmed booking
            self.release_slot_lock(slot.slot_id)
            return booking
        except Exception as exc:
            self.release_slot_lock(slot.slot_id)
            raise exc


# Singleton booking scheduler
scheduler = BookingScheduler()
