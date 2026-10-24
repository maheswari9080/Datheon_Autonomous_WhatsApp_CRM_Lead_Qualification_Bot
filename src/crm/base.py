"""Abstract CRM Adapter Interface and Synchronization Models."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class CRMLeadPayload:
    """Normalized prospect payload for CRM synchronization."""

    phone_number: str
    contact_name: str | None
    company_name: str | None
    budget: float | None
    currency: str
    company_size: str | None
    business_problem: str | None
    urgency: str
    decision_maker: str
    qualification_status: str
    qualification_score: float | None
    conversation_state: str
    booking_status: str | None
    calendar_event_id: str | None
    meeting_url: str | None
    consent_given: bool
    is_escalated: bool
    notes: str | None


class CRMAdapterProtocol(Protocol):
    """Protocol for external CRM synchronization."""

    async def sync_lead(self, payload: CRMLeadPayload) -> dict[str, Any]:
        """Idempotently create or update a lead in external CRM.

        Returns:
            Dictionary containing {"external_record_id": str, "status": "SYNCED"}
        """
        ...
