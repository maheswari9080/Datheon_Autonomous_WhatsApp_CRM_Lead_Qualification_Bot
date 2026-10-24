"""Pydantic V2 schemas for AI lead extraction and qualification validation."""

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProblemUrgencyEnum(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DecisionMakerEnum(StrEnum):
    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"


class QualificationStatusEnum(StrEnum):
    QUALIFIED = "QUALIFIED"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ExtractedLeadData(BaseModel):
    """Structured lead attributes extracted from customer dialogue."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    contact_name: str | None = Field(default=None, description="Prospect full or first name")
    company_name: str | None = Field(
        default=None, description="Prospect business or organization name"
    )
    budget_amount: float | None = Field(
        default=None, description="Normalized numeric budget in standard currency"
    )
    budget_currency: str = Field(default="USD", description="3-letter ISO currency code")
    company_size: str | None = Field(
        default=None, description="Employee count or range (e.g., '10-50')"
    )
    business_problem: str | None = Field(
        default=None, description="Core pain point, workflow bottleneck, or goal"
    )
    urgency: ProblemUrgencyEnum = Field(default=ProblemUrgencyEnum.MEDIUM)
    decision_maker: DecisionMakerEnum = Field(default=DecisionMakerEnum.UNKNOWN)
    purchase_timeline: str | None = Field(
        default=None, description="Target timeline (e.g., 'Immediate', '3 months')"
    )

    @field_validator("budget_currency")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        v = v.strip().upper()
        if v in {"$", "US", "DOLLARS", "USD"}:
            return "USD"
        if v in {"€", "EUR", "EUROS"}:
            return "EUR"
        if v in {"£", "GBP", "POUNDS"}:
            return "GBP"
        return v if len(v) == 3 else "USD"

    @field_validator("budget_amount", mode="before")
    @classmethod
    def parse_numeric_budget(cls, v: str | float | int | None) -> float | None:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        # Handle string like "$50k" or "10,000" or "5000 USD"
        cleaned = str(v).lower().replace(",", "").replace("$", "").replace("usd", "").strip()
        multiplier = 1.0
        if "k" in cleaned:
            multiplier = 1000.0
            cleaned = cleaned.replace("k", "").strip()
        elif "m" in cleaned:
            multiplier = 1000000.0
            cleaned = cleaned.replace("m", "").strip()

        match = re.search(r"\d+(\.\d+)?", cleaned)
        if match:
            return float(match.group(0)) * multiplier
        return None


class LeadExtractionResult(BaseModel):
    """Complete schema-validated output from AI extraction engine."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    lead: ExtractedLeadData = Field(default_factory=ExtractedLeadData)
    qualification_status: QualificationStatusEnum = Field(
        default=QualificationStatusEnum.NEEDS_MORE_INFORMATION
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0, default=0.5, description="Model confidence in extracted attributes"
    )
    missing_information: list[str] = Field(
        default_factory=list, description="Mandatory business fields still missing"
    )
    next_recommended_question: str | None = Field(
        default=None,
        description="Single concise follow-up question to present to the user",
    )
    is_adversarial: bool = Field(
        default=False, description="Flagged if prompt injection or override attempt detected"
    )
    customer_sentiment_score: float = Field(
        ge=-1.0,
        le=1.0,
        default=0.0,
        description="Sentiment polarity (-1.0 = furious, +1.0 = delighted)",
    )

    @model_validator(mode="after")
    def validate_single_followup(self) -> "LeadExtractionResult":
        """Enforce strict business requirement: maximum of 1 follow-up question per conversational turn."""
        if self.next_recommended_question:
            # Prevent multi-question bloat
            questions = [q.strip() for q in self.next_recommended_question.split("?") if q.strip()]
            if len(questions) > 1:
                # Truncate to first question
                self.next_recommended_question = f"{questions[0]}?"
        return self
