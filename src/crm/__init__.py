"""CRM and Transactional Outbox package."""

from src.crm.airtable import AirtableCRMAdapter, crm_adapter
from src.crm.base import CRMAdapterProtocol, CRMLeadPayload
from src.crm.outbox import TransactionalOutboxWorker, outbox_worker

__all__ = [
    "CRMAdapterProtocol",
    "CRMLeadPayload",
    "AirtableCRMAdapter",
    "crm_adapter",
    "TransactionalOutboxWorker",
    "outbox_worker",
]
