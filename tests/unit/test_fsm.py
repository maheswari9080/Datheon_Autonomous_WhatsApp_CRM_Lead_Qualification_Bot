"""Unit tests for the conversation Finite State Machine (FSM)."""

import pytest
from src.core.exceptions import InvalidStateTransitionError
from src.fsm.machine import ConversationFSM
from src.fsm.states import ConversationState


def test_standard_qualification_lifecycle():
    """Verify standard happy path progression: NEW -> GREETING -> DISCOVERY -> QUALIFICATION -> QUALIFIED -> BOOKING -> BOOKED -> CLOSED."""
    state = ConversationState.NEW
    metadata = {}

    state, metadata = ConversationFSM.transition(state, ConversationState.GREETING, metadata, reason="Inbound greeting")
    assert state == ConversationState.GREETING

    state, metadata = ConversationFSM.transition(state, ConversationState.DISCOVERY, metadata, reason="Customer responded")
    assert state == ConversationState.DISCOVERY

    state, metadata = ConversationFSM.transition(state, ConversationState.QUALIFICATION, metadata, reason="Business problem stated")
    assert state == ConversationState.QUALIFICATION

    state, metadata = ConversationFSM.transition(state, ConversationState.QUALIFIED, metadata, reason="All criteria satisfied")
    assert state == ConversationState.QUALIFIED

    state, metadata = ConversationFSM.transition(state, ConversationState.BOOKING, metadata, reason="Slot offered")
    assert state == ConversationState.BOOKING

    state, metadata = ConversationFSM.transition(state, ConversationState.BOOKED, metadata, reason="Slot confirmed")
    assert state == ConversationState.BOOKED

    state, metadata = ConversationFSM.transition(state, ConversationState.CLOSED, metadata, reason="Workflow complete")
    assert state == ConversationState.CLOSED

    # Check history was recorded
    assert len(metadata["state_history"]) == 7
    assert metadata["state_history"][0]["from"] == "NEW"
    assert metadata["state_history"][-1]["to"] == "CLOSED"


def test_needs_information_loop():
    """Verify discovery -> qualification -> needs_information -> qualification loop."""
    state = ConversationState.QUALIFICATION
    metadata = {}

    state, metadata = ConversationFSM.transition(
        state, ConversationState.NEEDS_INFORMATION, metadata, reason="Missing budget"
    )
    assert state == ConversationState.NEEDS_INFORMATION

    state, metadata = ConversationFSM.transition(
        state, ConversationState.QUALIFICATION, metadata, reason="Budget provided"
    )
    assert state == ConversationState.QUALIFICATION


def test_disqualification_lifecycle():
    """Verify transition from QUALIFICATION to NOT_QUALIFIED and CLOSED."""
    state = ConversationState.QUALIFICATION
    state, metadata = ConversationFSM.transition(
        state, ConversationState.NOT_QUALIFIED, reason="Budget below threshold"
    )
    assert state == ConversationState.NOT_QUALIFIED

    state, metadata = ConversationFSM.transition(
        state, ConversationState.CLOSED, metadata, reason="Closed after disqualification"
    )
    assert state == ConversationState.CLOSED


def test_human_handoff_from_arbitrary_state():
    """Verify that human handoff is permitted from any active state."""
    states_to_test = [
        ConversationState.NEW,
        ConversationState.GREETING,
        ConversationState.DISCOVERY,
        ConversationState.QUALIFICATION,
        ConversationState.NEEDS_INFORMATION,
        ConversationState.QUALIFIED,
        ConversationState.BOOKING,
    ]
    for s in states_to_test:
        assert ConversationFSM.is_legal_transition(s, ConversationState.HUMAN_HANDOFF)
        new_state, _ = ConversationFSM.transition(s, ConversationState.HUMAN_HANDOFF, reason="Explicit request")
        assert new_state == ConversationState.HUMAN_HANDOFF


def test_illegal_transition_rejection():
    """Verify that jumping across illegal states raises InvalidStateTransitionError."""
    # Cannot jump directly from NEW to BOOKED
    assert not ConversationFSM.is_legal_transition(ConversationState.NEW, ConversationState.BOOKED)
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        ConversationFSM.transition(ConversationState.NEW, ConversationState.BOOKED, reason="Illegal jump")
    assert "Illegal transition from 'NEW' to 'BOOKED'" in str(exc_info.value)

    # Cannot jump from DISCOVERY directly to BOOKING
    assert not ConversationFSM.is_legal_transition(ConversationState.DISCOVERY, ConversationState.BOOKING)
    with pytest.raises(InvalidStateTransitionError):
        ConversationFSM.transition(ConversationState.DISCOVERY, ConversationState.BOOKING)


def test_resume_from_human_handoff():
    """Verify operator resumption from HUMAN_HANDOFF back to DISCOVERY."""
    state = ConversationState.HUMAN_HANDOFF
    assert ConversationFSM.is_legal_transition(state, ConversationState.DISCOVERY)
    new_state, _ = ConversationFSM.transition(state, ConversationState.DISCOVERY, reason="Agent resumed bot")
    assert new_state == ConversationState.DISCOVERY
