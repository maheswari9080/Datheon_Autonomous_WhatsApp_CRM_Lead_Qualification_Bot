"""Input sanitization, prompt injection guardrails, and adversarial defenses."""

import re

from src.core.logging import get_logger

logger = get_logger(__name__)

# Patterns matching prompt injection, jailbreaks, and system override attempts
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(\w+\s+)?(rules|criteria|policies)", re.IGNORECASE),
    re.compile(r"system\s+override", re.IGNORECASE),
    re.compile(r"bypass\s+(qualification|verification|auth)", re.IGNORECASE),
    re.compile(
        r"you\s+are\s+now\s+(in\s+developer\s+mode|dan|an\s+unrestricted\s+ai)", re.IGNORECASE
    ),
    re.compile(
        r"format\s+drive|drop\s+table|delete\s+from|<\s*script.*?>|<\s*/\s*script\s*>",
        re.IGNORECASE,
    ),
    re.compile(r"grant\s+admin|sudo\s+make", re.IGNORECASE),
]


class InputGuardrails:
    """Sanitizes customer inbound text and prevents adversarial prompt manipulation."""

    @classmethod
    def inspect_and_sanitize(cls, text: str) -> tuple[str, bool, str | None]:
        """Inspect inbound text for prompt injection and security risks.

        Args:
            text: Raw customer message text.

        Returns:
            Tuple of (sanitized_text, is_malicious, reason)
        """
        if not text:
            return "", False, None

        cleaned = text.strip()

        # Check for injection attacks
        for pattern in INJECTION_PATTERNS:
            match = pattern.search(cleaned)
            if match:
                matched_phrase = match.group(0)
                reason = f"Prompt injection pattern detected: '{matched_phrase}'"
                logger.warning(
                    f"Adversarial input blocked: {reason}",
                    extra={"extra_fields": {"pattern": matched_phrase}},
                )
                return cleaned, True, reason

        return cleaned, False, None

    @classmethod
    def detect_conflicting_answers(
        cls, current_budget: float | None, new_budget: float | None
    ) -> bool:
        """Detect severe contradictions in customer answers across turns."""
        if current_budget is not None and new_budget is not None:
            # If budget changes by more than 10x or 90% drops, flag contradiction
            if new_budget > current_budget * 10 or new_budget < current_budget * 0.1:
                logger.info(
                    f"Contradictory budget detected: prior={current_budget}, new={new_budget}"
                )
                return True
        return False
