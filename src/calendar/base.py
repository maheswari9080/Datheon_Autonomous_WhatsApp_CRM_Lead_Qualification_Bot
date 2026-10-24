"""Abstract Calendar Adapter Interface and Data Models."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol


@dataclass
class TimeSlot:
    """Individual selectable appointment time slot."""

    slot_id: str
    start_time: datetime
    end_time: datetime
    formatted_display: str


class CalendarAdapterProtocol(Protocol):
    """Protocol defining required calendar operations."""

    async def get_available_slots(
        self,
        start_date: date,
        days: int = 3,
        timezone_str: str = "UTC",
    ) -> list[TimeSlot]:
        """Fetch real available slots conforming to business hours and buffers."""
        ...

    async def create_booking(
        self,
        lead_name: str,
        lead_phone: str,
        start_time: datetime,
        end_time: datetime,
        summary: str,
    ) -> dict[str, Any]:
        """Book a confirmed calendar demonstration event.

        Returns:
            Dictionary containing event_id, meeting_url, and status.
        """
        ...

    async def cancel_booking(self, external_event_id: str) -> bool:
        """Cancel an existing calendar appointment."""
        ...
