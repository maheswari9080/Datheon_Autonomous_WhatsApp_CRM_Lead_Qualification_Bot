"""Application exception hierarchy."""

from typing import Any


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SecurityException(AppException):
    """Raised on security violation (e.g. invalid signature, forbidden access)."""

    pass


class InvalidWebhookSignatureError(SecurityException):
    """Raised when X-Hub-Signature-256 HMAC verification fails."""

    pass


class WebhookVerificationError(SecurityException):
    """Raised when GET webhook hub challenge verification fails."""

    pass


class InvalidStateTransitionError(AppException):
    """Raised when an illegal FSM state transition is attempted."""

    def __init__(self, current_state: str, attempted_state: str, reason: str = ""):
        msg = f"Illegal transition from '{current_state}' to '{attempted_state}'. {reason}".strip()
        super().__init__(
            msg,
            {"current_state": current_state, "attempted_state": attempted_state, "reason": reason},
        )


class LLMProviderError(AppException):
    """Raised when external LLM call fails or times out."""

    pass


class PromptInjectionDetectedError(SecurityException):
    """Raised when malicious adversarial prompt or system override is detected."""

    pass


class CalendarSlotUnavailableError(AppException):
    """Raised when requested calendar slot is booked or invalid."""

    pass


class CRMSynchronizationError(AppException):
    """Raised when CRM API call fails or yields partial sync."""

    pass


class HumanHandoffRequired(AppException):
    """Raised when conversation requires immediate human intervention."""

    def __init__(self, reason: str, conversation_id: str, context: dict[str, Any] | None = None):
        super().__init__(
            f"Human handoff triggered for conversation {conversation_id}: {reason}", context
        )
        self.reason = reason
        self.conversation_id = conversation_id
