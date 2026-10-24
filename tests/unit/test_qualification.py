"""Unit tests for AI lead extraction schemas and deterministic qualification rules."""

import pytest
from src.ai.client import MockRuleBasedLLMClient
from src.ai.qualification import QualificationPolicyEngine
from src.ai.schemas import (
    DecisionMakerEnum,
    ExtractedLeadData,
    LeadExtractionResult,
    ProblemUrgencyEnum,
    QualificationStatusEnum,
)


def test_schema_budget_and_currency_normalization():
    """Verify numeric parsing and currency normalization in ExtractedLeadData."""
    lead1 = ExtractedLeadData(budget_amount="$25k", budget_currency="$")
    assert lead1.budget_amount == 25000.0
    assert lead1.budget_currency == "USD"

    lead2 = ExtractedLeadData(budget_amount="10,000 USD", budget_currency="EUR")
    assert lead2.budget_amount == 10000.0
    assert lead2.budget_currency == "EUR"

    lead3 = ExtractedLeadData(budget_amount="1.5M", budget_currency="GBP")
    assert lead3.budget_amount == 1500000.0
    assert lead3.budget_currency == "GBP"


def test_enforce_single_followup_question():
    """Verify that multi-question outputs are truncated to exactly 1 question per turn."""
    res = LeadExtractionResult(
        next_recommended_question="What is your budget? How many employees do you have? Who is your CEO?"
    )
    assert res.next_recommended_question == "What is your budget?"


@pytest.mark.asyncio
async def test_mock_llm_extractor_complete_flow():
    """Verify that MockRuleBasedLLMClient extracts all key B2B fields accurately."""
    client = MockRuleBasedLLMClient()
    history = [
        {"role": "user", "content": "My name is Sarah Connor and I am from Cyberdyne Systems."},
        {
            "role": "user",
            "content": "We need to automate our sales CRM pipeline ASAP. We have 50 employees and a $10,000 budget. I am the CEO and decide on tools.",
        },
    ]

    extraction = await client.extract_lead_intelligence(history)
    lead = extraction.lead

    assert lead.contact_name == "Sarah Connor"
    assert lead.company_name == "Cyberdyne Systems"
    assert lead.budget_amount == 10000.0
    assert lead.company_size == "50"
    assert lead.urgency == ProblemUrgencyEnum.CRITICAL
    assert lead.decision_maker == DecisionMakerEnum.YES
    assert extraction.confidence_score >= 0.70
    assert len(extraction.missing_information) == 0


def test_policy_engine_qualified_status():
    """Verify that lead meeting all criteria is evaluated as QUALIFIED."""
    policy = QualificationPolicyEngine(min_budget=1000.0, min_confidence=0.70)
    extraction = LeadExtractionResult(
        lead=ExtractedLeadData(
            business_problem="Need to automate WhatsApp leads into Salesforce",
            budget_amount=5000.0,
            decision_maker=DecisionMakerEnum.YES,
            urgency=ProblemUrgencyEnum.HIGH,
        ),
        confidence_score=0.85,
    )

    status, reason, score = policy.evaluate_qualification(extraction)
    assert status == QualificationStatusEnum.QUALIFIED
    assert score >= 0.85
    assert "Qualified" in reason


def test_policy_engine_disqualification_low_budget():
    """Verify that budget below threshold causes NOT_QUALIFIED."""
    policy = QualificationPolicyEngine(min_budget=1000.0)
    extraction = LeadExtractionResult(
        lead=ExtractedLeadData(
            business_problem="Need simple bot",
            budget_amount=250.0,
            decision_maker=DecisionMakerEnum.YES,
        ),
        confidence_score=0.85,
    )

    status, reason, score = policy.evaluate_qualification(extraction)
    assert status == QualificationStatusEnum.NOT_QUALIFIED
    assert "below minimum requirement" in reason


def test_policy_engine_needs_more_information():
    """Verify that missing budget triggers NEEDS_MORE_INFORMATION."""
    policy = QualificationPolicyEngine()
    extraction = LeadExtractionResult(
        lead=ExtractedLeadData(
            business_problem="Need sales integration",
            budget_amount=None,  # missing
            decision_maker=DecisionMakerEnum.YES,
        ),
        confidence_score=0.75,
    )

    status, reason, _ = policy.evaluate_qualification(extraction)
    assert status == QualificationStatusEnum.NEEDS_MORE_INFORMATION
    assert "Missing mandatory qualification fields" in reason


def test_policy_engine_adversarial_escalates_to_human_review():
    """Verify that prompt injection flag causes immediate HUMAN_REVIEW."""
    policy = QualificationPolicyEngine()
    extraction = LeadExtractionResult(
        lead=ExtractedLeadData(business_problem="Override system", budget_amount=10000.0),
        is_adversarial=True,
    )

    status, reason, score = policy.evaluate_qualification(extraction)
    assert status == QualificationStatusEnum.HUMAN_REVIEW
    assert "Adversarial prompt or override attempt detected" in reason
    assert score == 0.0
