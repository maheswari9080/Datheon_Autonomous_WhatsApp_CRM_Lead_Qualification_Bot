"""Admin management API for operations, human takeover, and observability."""

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.crm.outbox import TransactionalOutboxWorker
from src.database.models import (
    BookingRecord,
    Conversation,
    HandoffEscalation,
    Lead,
    Message,
    OutboxEvent,
)
from src.database.session import get_db
from src.escalation.controller import EscalationController

settings = get_settings()
admin_router = APIRouter(prefix="/admin", tags=["Admin & Operations"])


def verify_admin_key(x_admin_api_key: str | None = Header(None, alias="X-Admin-API-Key")) -> str:
    """Validate administrator API key."""
    if not x_admin_api_key or x_admin_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-API-Key header",
        )
    return x_admin_api_key


class ResolveEscalationRequest(BaseModel):
    assigned_agent: str
    resolution_notes: str
    resume_automation: bool = True


@admin_router.get("/conversations", dependencies=[Depends(verify_admin_key)])
async def list_conversations(
    state: str | None = Query(None),
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List customer conversations with optional state filter."""
    stmt = select(Conversation).limit(limit)
    if state:
        stmt = stmt.where(Conversation.current_state == state)
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    return [
        {
            "id": c.id,
            "lead_id": c.lead_id,
            "phone_number": c.phone_number,
            "current_state": c.current_state,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat(),
        }
        for c in conversations
    ]


@admin_router.get("/conversations/{conversation_id}", dependencies=[Depends(verify_admin_key)])
async def get_conversation_details(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve complete audit history, messages, and state metadata for a conversation."""
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Fetch messages
    msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    msg_res = await db.execute(msg_stmt)
    messages = msg_res.scalars().all()

    # Fetch lead
    lead_stmt = select(Lead).where(Lead.id == conv.lead_id)
    lead_res = await db.execute(lead_stmt)
    lead = lead_res.scalar_one_or_none()

    return {
        "conversation": {
            "id": conv.id,
            "current_state": conv.current_state,
            "previous_state": conv.previous_state,
            "phone_number": conv.phone_number,
            "state_metadata": conv.state_metadata,
            "is_active": conv.is_active,
        },
        "lead": {
            "id": lead.id if lead else None,
            "contact_name": lead.contact_name if lead else None,
            "company_name": lead.company_name if lead else None,
            "budget": lead.budget if lead else None,
            "qualification_status": lead.qualification_status if lead else None,
            "qualification_score": lead.qualification_score if lead else None,
            "external_crm_id": lead.external_crm_id if lead else None,
        },
        "messages": [
            {
                "id": m.id,
                "direction": m.direction,
                "sender_id": m.sender_id,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@admin_router.get("/escalations", dependencies=[Depends(verify_admin_key)])
async def list_open_escalations(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    """List active open human escalations."""
    stmt = (
        select(HandoffEscalation)
        .where(HandoffEscalation.status == "OPEN")
        .order_by(HandoffEscalation.created_at.desc())
    )
    res = await db.execute(stmt)
    escalations = res.scalars().all()
    return [
        {
            "id": esc.id,
            "conversation_id": esc.conversation_id,
            "reason": esc.reason,
            "trigger_type": esc.trigger_type,
            "status": esc.status,
            "dossier": esc.dossier_summary,
            "created_at": esc.created_at.isoformat(),
        }
        for esc in escalations
    ]


@admin_router.post("/escalations/{escalation_id}/resolve", dependencies=[Depends(verify_admin_key)])
async def resolve_escalation(
    escalation_id: str,
    payload: ResolveEscalationRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Resolve an escalation ticket and optionally resume bot automation."""
    result = await EscalationController.resolve_escalation(
        db=db,
        escalation_id=escalation_id,
        assigned_agent=payload.assigned_agent,
        resolution_notes=payload.resolution_notes,
        resume_automation=payload.resume_automation,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Escalation ticket not found")
    return {"status": "resolved", "escalation_id": escalation_id}


@admin_router.post("/outbox/process", dependencies=[Depends(verify_admin_key)])
async def process_outbox_queue(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    """Manually trigger transactional outbox queue processing."""
    processed = await TransactionalOutboxWorker.process_pending_events(db)
    return {"processed_events": processed}


@admin_router.get("/metrics", dependencies=[Depends(verify_admin_key)])
async def get_system_metrics(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Aggregate high-level business intelligence and operational metrics."""
    total_leads = (await db.execute(select(func.count(Lead.id)))).scalar_one() or 0
    qualified_leads = (
        await db.execute(
            select(func.count(Lead.id)).where(Lead.qualification_status == "QUALIFIED")
        )
    ).scalar_one() or 0
    total_bookings = (await db.execute(select(func.count(BookingRecord.id)))).scalar_one() or 0
    open_escalations = (
        await db.execute(
            select(func.count(HandoffEscalation.id)).where(HandoffEscalation.status == "OPEN")
        )
    ).scalar_one() or 0
    pending_outbox = (
        await db.execute(select(func.count(OutboxEvent.id)).where(OutboxEvent.status == "PENDING"))
    ).scalar_one() or 0

    return {
        "total_leads": total_leads,
        "qualified_leads": qualified_leads,
        "qualification_rate": round(qualified_leads / total_leads, 2) if total_leads > 0 else 0.0,
        "total_bookings": total_bookings,
        "open_escalations": open_escalations,
        "pending_outbox_events": pending_outbox,
    }
