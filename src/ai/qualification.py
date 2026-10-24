"""Deterministic B2B Lead Qualification Policy Engine."""

from typing import Any
from src.ai.schemas import (
    DecisionMakerEnum,
    ExtractedLeadData,
    LeadExtractionResult,
    ProblemUrgencyEnum,
    QualificationStatusEnum,
)
from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class QualificationPolicyEngine:
    """Evaluates extracted lead data against configurable B2B qualification rules.
    
    Guarantees deterministic decision-making:
    - LLM provides extracted signals and suggestions.
    - Python backend enforces strict policy thresholds before authorizing booking or CRM sync.
    """

    def __init__(
        self,
        min_budget: float | None = None,
        min_confidence: float | None = None,
        require_decision_maker: bool = True,
    ):
        self.min_budget = min_budget if min_budget is not None else settings.MIN_QUALIFICATION_BUDGET
        self.min_confidence = min_confidence if min_confidence is not None else settings.QUALIFICATION_CONFIDENCE_THRESHOLD
        self.require_decision_maker = require_decision_maker

    def evaluate_qualification(self, extraction: LeadExtractionResult) -> tuple[QualificationStatusEnum, str, float]:
        """Evaluate extracted lead data against deterministic business criteria.
        
        Returns:
            Tuple of (QualificationStatusEnum, reasoning_summary, score)
        """
        lead = extraction.lead

        # 1. Adversarial / Prompt Injection guard -> Immediate HUMAN_REVIEW
        if extraction.is_adversarial:
            return (
                QualificationStatusEnum.HUMAN_REVIEW,
                "Adversarial prompt or override attempt detected; escalation triggered.",
                0.0,
            )

        # 2. Check Disqualification (Explicit failure of policy criteria)
        if lead.budget_amount is not None and lead.budget_amount < self.min_budget:
            reason = f"Allocated budget (${lead.budget_amount:,.2f}) is below minimum requirement (${self.min_budget:,.2f})."
            logger.info(f"Lead disqualified: {reason}")
            return QualificationStatusEnum.NOT_QUALIFIED, reason, 0.2

        # 3. Check for Missing Mandatory Information
        missing_fields: list[str] = []
        if not lead.business_problem:
            missing_fields.append("business problem")
        if lead.budget_amount is None:
            missing_fields.append("budget")
        if self.require_decision_maker and lead.decision_maker == DecisionMakerEnum.UNKNOWN:
            missing_fields.append("decision maker status")

        if missing_fields:
            reason = f"Missing mandatory qualification fields: {', '.join(missing_fields)}."
            logger.info(f"Lead needs more info: {reason}")
            return QualificationStatusEnum.NEEDS_MORE_INFORMATION, reason, 0.5

        # 4. Check Non-Decision Maker / Delegation -> Human review
        if lead.decision_maker == DecisionMakerEnum.NO:
            reason = "Prospect explicitly stated they are not the decision maker; routed for human sales qualification."
            return QualificationStatusEnum.HUMAN_REVIEW, reason, 0.65

        # 5. Check Confidence Threshold
        if extraction.confidence_score < self.min_confidence:
            reason = f"Extraction confidence score ({extraction.confidence_score:.2f}) below threshold ({self.min_confidence:.2f})."
            return QualificationStatusEnum.NEEDS_MORE_INFORMATION, reason, extraction.confidence_score

        # 6. Fully Qualified Lead
        score = 0.85
        if lead.urgency in {ProblemUrgencyEnum.HIGH, ProblemUrgencyEnum.CRITICAL}:
            score += 0.10
        if lead.budget_amount and lead.budget_amount >= self.min_budget * 2:
            score += 0.05
        score = min(1.0, score)

        reason = (
            f"Qualified: Budget ${lead.budget_amount:,.2f} satisfies minimum ${self.min_budget:,.2f}, "
            f"pain point established, decision maker confirmed (urgency: {lead.urgency.value})."
        )
        logger.info(f"Lead successfully qualified: {reason}")
        return QualificationStatusEnum.QUALIFIED, reason, score


# Singleton policy engine instance
policy_engine = QualificationPolicyEngine()
