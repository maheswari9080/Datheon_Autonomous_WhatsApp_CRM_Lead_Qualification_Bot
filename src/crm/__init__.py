"""CRM synchronization package."""

from src.crm.airtable import AirtableCRMAdapter, crm_adapter
from src.crm.base import CRMAdapterProtocol, CRMLeadPayload

__all__ = ["CRMAdapterProtocol", "CRMLeadPayload", "AirtableCRMAdapter", "crm_adapter"]
