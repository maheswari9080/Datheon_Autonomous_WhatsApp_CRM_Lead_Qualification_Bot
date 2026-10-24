"""Human Handoff and Escalation Controller."""

from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.crm.outbox import TransactionalOutboxWorker
from src.database.models import Conversation, HandoffEscalation, Lead
from src.escalation.notifier import notifier
from src.escalation.sentiment import SentimentDetector
from src.fsm.machine import ConversationFSM
from src.fsm.states import ConversationState

logger = get_logger(__name__)


class EscalationController:
    """Manages escalation lifecycle, human takeover, and resume workflows."""

    @classmethod
    def should_escalate(
        cls,
        text: str,
        model_sentiment: float = 0.0,
        consecutive_failures: int = 0,
        is_adversarial: bool = False,
    ) -> tuple[bool, str, str]:
        """Check all triggers for escalation.
        
        Returns:
            Tuple of (should_escalate, trigger_type, reason)
        """
        if is_adversarial:
            return True, "ADVERSARIAL_ATTACK", "Malicious prompt override detected"

        if SentimentDetector.is_explicit_human_request(text):
            return True, "EXPLICIT_REQUEST", "Customer explicitly asked for a human agent"

        if SentimentDetector.is_severe_frustration(text, model_sentiment):
            return True, "NEGATIVE_SENTIMENT", "Customer expressing high frustration or annoyance"

        if consecutive_failures >= 3:
            return True, "REPEATED_FAILURE", "Assistant repeatedly failed to extract required information"

        return False, "NONE", ""

    @classmethod
    async def trigger_handoff(
        cls,
        db: AsyncSession,
        conversation: Conversation,
        lead: Lead,
        trigger_type: str,
        reason: str,
        recent_dialogue: list[dict[str, str]] | None = None,
    ) -> HandoffEscalation:
        """Execute full human takeover: halts autonomous actions, logs escalation, and alerts team."""
        # 1. Advance FSM state to HUMAN_HANDOFF
        new_state, updated_meta = ConversationFSM.transition(
            conversation.current_state,
            ConversationState.HUMAN_HANDOFF,
            conversation.state_metadata,
            reason=f"Escalation [{trigger_type}]: {reason}",
        )
        conversation.previous_state = conversation.current_state
        conversation.current_state = new_state.value
        conversation.state_metadata = updated_meta

        # 2. Build Briefing Dossier
        dossier = {
            "contact_name": lead.contact_name,
            "company_name": lead.company_name,
            "budget": lead.budget,
            "qualification_status": lead.qualification_status,
            "urgency": lead.urgency,
            "phone_number": lead.phone_number,
            "dialogue_history": recent_dialogue or [],
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

        # 3. Create persistent HandoffEscalation record
        escalation = HandoffEscalation(
            conversation_id=conversation.id,
            reason=reason,
            trigger_type=trigger_type,
            status="OPEN",
            dossier_summary=dossier,
        )
        db.add(escalation)
        await db.flush()

        # 4. Enqueue polite single acknowledgment to customer (ceasing sales actions)
        ack_message = (
            "I have connected you with our human team. "
            "A product specialist will review your request and follow up with you shortly."
        )
        await TransactionalOutboxWorker.enqueue_event(
            db,
            event_type="WHATSAPP_DISPATCH",
            payload={"recipient_phone": lead.phone_number, "message_body": ack_message},
        )

        # 5. Alert internal team via Slack
        await notifier.dispatch_slack_alert(
            incident_id=escalation.id,
            phone_number=lead.phone_number,
            reason=reason,
            dossier=dossier,
        )

        logger.info(
            f"Human handoff active for conversation {conversation.id} (Escalation ID: {escalation.id})"
        )
        return escalation

    @classmethod
    async def resolve_escalation(
        cls,
        db: AsyncSession,
        escalation_id: str,
        assigned_agent: str,
        resolution_notes: str,
        resume_automation: bool = True,
    ) -> HandoffEscalation | None:
        """Operator action to resolve escalation and optionally resume bot automation."""
        stmt = select(HandoffEscalation).where(HandoffEscalation.id == escalation_id)
        result = await db.execute(stmt)
        escalation = result.scalar_one_or_none()

        if not escalation:
            return None

        escalation.status = "RESOLVED"
        escalation.assigned_agent = assigned_agent
        escalation.resolution_notes = resolution_notes
        escalation.resolved_at = datetime.now(timezone.utc)

        # Check if we should resume bot automation
        if resume_automation:
            conv_stmt = select(Conversation).where(Conversation.id == escalation.conversation_id)
            conv_res = await db.execute(conv_stmt)
            conversation = conv_res.scalar_one_or_none()
            if conversation and conversation.current_state == ConversationState.HUMAN_HANDOFF.value:
                new_state, updated_meta = ConversationFSM.transition(
                    conversation.current_state,
                    ConversationState.DISCOVERY,
                    conversation.state_metadata,
                    reason=f"Operator {assigned_agent} resolved escalation and resumed bot",
                )
                conversation.previous_state = conversation.current_state
                conversation.current_state = new_state.value
                conversation.state_metadata = updated_meta

        await db.commit()
        return escalation
