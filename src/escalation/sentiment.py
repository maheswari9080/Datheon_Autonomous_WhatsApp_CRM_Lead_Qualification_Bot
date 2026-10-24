"""Sentiment analyzer and explicit human request detector."""

import re

HUMAN_REQUEST_PATTERNS = [
    re.compile(r"\b(talk\s+to\s+(a\s+)?(human|agent|person|representative|operator|manager))\b", re.IGNORECASE),
    re.compile(r"\b(speak\s+with\s+(a\s+)?(human|agent|person|representative))\b", re.IGNORECASE),
    re.compile(r"\b(i\s+want\s+(a\s+)?human)\b", re.IGNORECASE),
    re.compile(r"\b(connect\s+me\s+to\s+(an?\s+)?(agent|human|representative))\b", re.IGNORECASE),
    re.compile(r"\b((reach|contact|get|transfer to|connect( me)? to|i need)\s+(customer|human)\s+support)\b", re.IGNORECASE),
]

FRUSTRATION_PATTERNS = [
    re.compile(r"\b(stupid\s+bot|useless\s+bot|idiot|annoying|scam|hate\s+this|terrible\s+service)\b", re.IGNORECASE),
    re.compile(r"\b(stop\s+asking\s+me|already\s+told\s+you|waste\s+of\s+time)\b", re.IGNORECASE),
]


class SentimentDetector:
    """Analyzes customer messages for frustration and explicit human escalation triggers."""

    @classmethod
    def is_explicit_human_request(cls, text: str) -> bool:
        """Check if message contains direct intent to bypass bot and reach a human."""
        if not text:
            return False
        return any(pat.search(text) for pat in HUMAN_REQUEST_PATTERNS)

    @classmethod
    def is_severe_frustration(cls, text: str, model_sentiment: float = 0.0) -> bool:
        """Check for severe customer frustration via pattern matching or sentiment score."""
        if not text:
            return False
        if model_sentiment <= -0.6:
            return True
        return any(pat.search(text) for pat in FRUSTRATION_PATTERNS)
