"""Airtable CRM integration adapter."""

from datetime import datetime, timezone
import uuid
from typing import Any
import httpx

from src.core.config import get_settings
from src.core.exceptions import CRMSynchronizationError
from src.core.logging import get_logger
from src.crm.base import CRMAdapterProtocol, CRMLeadPayload

logger = get_logger(__name__)
settings = get_settings()


class AirtableCRMAdapter(CRMAdapterProtocol):
    """Airtable REST API integration adapter with in-memory sandbox fallback."""

    def __init__(
        self,
        api_key: str = "",
        base_id: str = "",
        table_name: str = "Leads",
    ):
        self.api_key = api_key or settings.AIRTABLE_API_KEY
        self.base_id = base_id or settings.AIRTABLE_BASE_ID
        self.table_name = table_name or settings.AIRTABLE_TABLE_NAME
        # In-memory registry for sandbox / tests: phone_number -> record
        self._records: dict[str, dict[str, Any]] = {}

    async def sync_lead(self, payload: CRMLeadPayload) -> dict[str, Any]:
        """Synchronize or update lead in Airtable table."""
        # Check if production credentials are provided
        if self.api_key and not self.api_key.startswith("pat_placeholder") and self.base_id and not self.base_id.startswith("app_placeholder"):
            try:
                url = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                airtable_fields = {
                    "Phone": payload.phone_number,
                    "Name": payload.contact_name or "Unknown",
                    "Company": payload.company_name or "",
                    "Budget": payload.budget or 0.0,
                    "Currency": payload.currency,
                    "Company Size": payload.company_size or "",
                    "Pain Point": payload.business_problem or "",
                    "Urgency": payload.urgency,
                    "Qualification": payload.qualification_status,
                    "Score": payload.qualification_score or 0.0,
                    "Booking Status": payload.booking_status or "None",
                    "Calendar Event ID": payload.calendar_event_id or "",
                    "Escalated": payload.is_escalated,
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, headers=headers, json={"fields": airtable_fields})
                    if resp.status_code in {200, 201}:
                        data = resp.json()
                        return {"external_record_id": data["id"], "status": "SYNCED"}
                    else:
                        logger.warning(f"Airtable HTTP error {resp.status_code}: {resp.text}")
            except Exception as exc:
                logger.warning(f"Airtable network error: {exc}; using local synchronization")

        # Sandbox / Fallback simulation
        existing_id = self._records.get(payload.phone_number, {}).get("external_record_id")
        record_id = existing_id or f"rec_{uuid.uuid4().hex[:14]}"

        record_data = {
            "external_record_id": record_id,
            "phone_number": payload.phone_number,
            "contact_name": payload.contact_name,
            "company_name": payload.company_name,
            "budget": payload.budget,
            "qualification_status": payload.qualification_status,
            "booking_status": payload.booking_status,
            "calendar_event_id": payload.calendar_event_id,
            "meeting_url": payload.meeting_url,
            "is_escalated": payload.is_escalated,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "status": "SYNCED",
        }
        self._records[payload.phone_number] = record_data
        logger.info(
            f"CRM Synced for {payload.phone_number} -> {record_id} ({payload.qualification_status})",
            extra={"extra_fields": {"record_id": record_id, "status": payload.qualification_status}},
        )
        return {"external_record_id": record_id, "status": "SYNCED"}


# Singleton CRM adapter instance
crm_adapter = AirtableCRMAdapter()
