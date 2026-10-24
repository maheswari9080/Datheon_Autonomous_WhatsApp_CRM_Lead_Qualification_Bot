"""Deterministic Conversation Finite State Machine (FSM)."""

from typing import Any

from src.core.exceptions import InvalidStateTransitionError
from src.core.logging import get_logger
from src.fsm.states import ConversationState

logger = get_logger(__name__)

# Explicit legal transitions mapping: source_state -> set of valid target states
LEGAL_TRANSITIONS: dict[ConversationState, set[ConversationState]] = {
    ConversationState.NEW: {
        ConversationState.GREETING,
        ConversationState.HUMAN_HANDOFF,
        ConversationState.PROCESSING_ERROR,
    },
    ConversationState.GREETING: {
        ConversationState.DISCOVERY,
        ConversationState.QUALIFICATION,
        ConversationState.NEEDS_INFORMATION,
        ConversationState.QUALIFIED,
        ConversationState.HUMAN_HANDOFF,
        ConversationState.PROCESSING_ERROR,
    },
    ConversationState.DISCOVERY: {
        ConversationState.QUALIFICATION,
        ConversationState.NEEDS_INFORMATION,
        ConversationState.QUALIFIED,
        ConversationState.NOT_QUALIFIED,
        ConversationState.HUMAN_HANDOFF,
        ConversationState.PROCESSING_ERROR,
    },
    ConversationState.QUALIFICATION: {
        ConversationState.NEEDS_INFORMATION,
        ConversationState.QUALIFIED,
        ConversationState.NOT_QUALIFIED,
        ConversationState.HUMAN_HANDOFF,
        ConversationState.PROCESSING_ERROR,
    },
    ConversationState.NEEDS_INFORMATION: {
        ConversationState.QUALIFICATION,
        ConversationState.QUALIFIED,
        ConversationState.NOT_QUALIFIED,
        ConversationState.DISCOVERY,
        ConversationState.HUMAN_HANDOFF,
        ConversationState.PROCESSING_ERROR,
    },
    ConversationState.QUALIFIED: {
        ConversationState.BOOKING,
        ConversationState.HUMAN_HANDOFF,
        ConversationState.PROCESSING_ERROR,
    },
    ConversationState.NOT_QUALIFIED: {
        ConversationState.CLOSED,
        ConversationState.HUMAN_HANDOFF,
        ConversationState.PROCESSING_ERROR,
    },
    ConversationState.BOOKING: {
        ConversationState.BOOKED,
        ConversationState.QUALIFIED,  # Fallback if slot becomes unavailable
        ConversationState.HUMAN_HANDOFF,
        ConversationState.PROCESSING_ERROR,
    },
    ConversationState.BOOKED: {
        ConversationState.CLOSED,
        ConversationState.HUMAN_HANDOFF,
        ConversationState.PROCESSING_ERROR,
    },
    ConversationState.CLOSED: {
        ConversationState.GREETING,  # Re-opening conversation on new message
        ConversationState.HUMAN_HANDOFF,
        ConversationState.PROCESSING_ERROR,
    },
    ConversationState.HUMAN_HANDOFF: {
        ConversationState.DISCOVERY,  # Operator manually resumes automation
        ConversationState.CLOSED,  # Operator completes ticket
        ConversationState.PROCESSING_ERROR,
    },
    ConversationState.PROCESSING_ERROR: {
        ConversationState.HUMAN_HANDOFF,
        ConversationState.DISCOVERY,
        ConversationState.CLOSED,
    },
}


class ConversationFSM:
    """Manages legal transitions, guards, and metadata updates for conversations."""

    @staticmethod
    def is_legal_transition(
        source: ConversationState | str, target: ConversationState | str
    ) -> bool:
        """Check whether a transition is permitted by the state table."""
        src_enum = ConversationState(source)
        tgt_enum = ConversationState(target)
        valid_targets = LEGAL_TRANSITIONS.get(src_enum, set())
        return tgt_enum in valid_targets

    @classmethod
    def transition(
        cls,
        current_state: ConversationState | str,
        target_state: ConversationState | str,
        current_metadata: dict[str, Any] | None = None,
        update_metadata: dict[str, Any] | None = None,
        reason: str = "",
    ) -> tuple[ConversationState, dict[str, Any]]:
        """Validate and execute a state transition.

        Returns:
            Tuple of (new_state, updated_metadata)

        Raises:
            InvalidStateTransitionError: If the transition violates FSM invariants.
        """
        src = ConversationState(current_state)
        tgt = ConversationState(target_state)
        metadata = dict(current_metadata or {})

        if not cls.is_legal_transition(src, tgt):
            logger.error(
                "Illegal transition rejected",
                extra={"extra_fields": {"from": src.value, "to": tgt.value, "reason": reason}},
            )
            raise InvalidStateTransitionError(src.value, tgt.value, reason=reason)

        if update_metadata:
            metadata.update(update_metadata)

        # Record transition history inside metadata
        history = metadata.setdefault("state_history", [])
        history.append(
            {
                "from": src.value,
                "to": tgt.value,
                "reason": reason,
            }
        )

        logger.info(
            f"FSM Transition: {src.value} -> {tgt.value}",
            extra={
                "extra_fields": {"from_state": src.value, "to_state": tgt.value, "reason": reason}
            },
        )
        return tgt, metadata
