"""Provider-independent LLM extraction client with deterministic fallback engine."""

import json
import re
from typing import Protocol

import httpx

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


class LLMClientProtocol(Protocol):
    """Protocol for provider-independent LLM extraction."""

    async def extract_lead_intelligence(
        self,
        conversation_history: list[dict[str, str]],
        existing_lead_data: ExtractedLeadData | None = None,
    ) -> LeadExtractionResult:
        """Extract structured business data from conversation turns."""
        ...


class MockRuleBasedLLMClient:
    """High-accuracy deterministic fallback & offline rule-based extraction engine."""

    async def extract_lead_intelligence(
        self,
        conversation_history: list[dict[str, str]],
        existing_lead_data: ExtractedLeadData | None = None,
    ) -> LeadExtractionResult:
        combined_text = " ".join([m.get("content", "") for m in conversation_history])
        lead = existing_lead_data.model_copy() if existing_lead_data else ExtractedLeadData()

        # 1. Adversarial / Prompt Injection detection
        adversarial_patterns = [
            r"ignore (all )?previous instructions",
            r"system override",
            r"bypass qualification",
            r"mark me as qualified",
            r"pretend to be",
            r"jailbreak",
        ]
        is_adversarial = any(
            re.search(pat, combined_text, re.IGNORECASE) for pat in adversarial_patterns
        )

        # 2. Sentiment analysis heuristic
        sentiment_score = 0.0
        if re.search(
            r"\b(angry|furious|terrible|useless|horrible|scam|hate|talk to human|agent now)\b",
            combined_text,
            re.IGNORECASE,
        ):
            sentiment_score = -0.8
        elif re.search(
            r"\b(great|awesome|love|excited|interested|helpful|thanks)\b",
            combined_text,
            re.IGNORECASE,
        ):
            sentiment_score = 0.7

        # 3. Contact & Company name extraction
        name_match = re.search(
            r"(?:my name is|i am|i'm|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            combined_text,
            re.IGNORECASE,
        )
        if name_match and not lead.contact_name:
            lead.contact_name = name_match.group(1).title()

        company_match = re.search(
            r"(?:at|from|company is|work with|represent)\s+([A-Z][a-zA-Z0-9_\-]+(?:\s+[A-Z][a-zA-Z0-9_\-]+)?)",
            combined_text,
            re.IGNORECASE,
        )
        if company_match and not lead.company_name:
            lead.company_name = company_match.group(1).title()

        # 4. Budget extraction (look for dollar sign, budget keyword, or explicit currency)
        budget_match = re.search(
            r"\$\s*(\d+(?:,\d+)*(?:\.\d+)?\s*(?:k|m)?)|(?:budget|allocated|funds)(?:\s*(?:is|of|around|about|:))?\s*\$?\s*(\d+(?:,\d+)*(?:\.\d+)?\s*(?:k|m|usd|dollars)?)|\b(\d+(?:,\d+)*(?:\.\d+)?\s*(?:k|m|usd|dollars))\b",
            combined_text,
            re.IGNORECASE,
        )
        if budget_match and not lead.budget_amount:
            raw_match = budget_match.group(1) or budget_match.group(2) or budget_match.group(3)
            if raw_match:
                parsed_val = ExtractedLeadData.parse_numeric_budget(raw_match)
                if parsed_val:
                    lead.budget_amount = parsed_val

        # 5. Company size extraction
        size_match = re.search(
            r"(\d+(?:-\d+)?|\d+\+)\s*(?:people|employees|team members|staff)",
            combined_text,
            re.IGNORECASE,
        )
        if size_match and not lead.company_size:
            lead.company_size = size_match.group(1)

        # 6. Business problem extraction
        if not lead.business_problem:
            prob_keywords = [
                "automate",
                "crm",
                "sales",
                "leads",
                "booking",
                "workflow",
                "integration",
                "pipeline",
            ]
            for kw in prob_keywords:
                if kw in combined_text.lower():
                    lead.business_problem = (
                        f"Customer seeks assistance with {kw} optimization and workflow automation."
                    )
                    break

        # 7. Urgency extraction
        if re.search(
            r"\b(asap|immediately|critical|urgent|emergency|today)\b", combined_text, re.IGNORECASE
        ):
            lead.urgency = ProblemUrgencyEnum.CRITICAL
        elif re.search(r"\b(soon|next week|this month)\b", combined_text, re.IGNORECASE):
            lead.urgency = ProblemUrgencyEnum.HIGH
        elif re.search(r"\b(exploring|curious|no rush)\b", combined_text, re.IGNORECASE):
            lead.urgency = ProblemUrgencyEnum.LOW

        # 8. Decision Maker extraction
        if re.search(
            r"\b(i decide|i'm the founder|ceo|cto|owner|director|vp|head of)\b",
            combined_text,
            re.IGNORECASE,
        ):
            lead.decision_maker = DecisionMakerEnum.YES
        elif re.search(
            r"\b(need approval|my boss|committee|checking for)\b", combined_text, re.IGNORECASE
        ):
            lead.decision_maker = DecisionMakerEnum.NO

        # 9. Purchase Timeline
        if re.search(
            r"\b(q1|q2|q3|q4|next month|immediate|within 30 days)\b", combined_text, re.IGNORECASE
        ):
            lead.purchase_timeline = "Within 30 days"

        # Determine missing fields
        missing: list[str] = []
        if not lead.business_problem:
            missing.append("business_problem")
        if lead.budget_amount is None:
            missing.append("budget_amount")
        if not lead.company_size:
            missing.append("company_size")
        if lead.decision_maker == DecisionMakerEnum.UNKNOWN:
            missing.append("decision_maker")

        # Select single recommended follow-up question
        next_question: str | None = None
        if "business_problem" in missing:
            next_question = "Could you tell me a little about the primary workflow challenge or sales bottleneck you're looking to solve?"
        elif "budget_amount" in missing:
            next_question = (
                "What approximate budget range do you have allocated for this initiative?"
            )
        elif "company_size" in missing:
            next_question = "How many team members or employees will be utilizing this platform?"
        elif "decision_maker" in missing:
            next_question = "Are you the primary decision-maker for evaluating and approving new software solutions?"

        # Confidence calculation
        filled_count = sum(
            1
            for v in [
                lead.contact_name,
                lead.business_problem,
                lead.budget_amount,
                lead.company_size,
            ]
            if v is not None
        )
        confidence = min(0.95, 0.40 + (filled_count * 0.15))

        return LeadExtractionResult(
            lead=lead,
            qualification_status=QualificationStatusEnum.NEEDS_MORE_INFORMATION
            if missing
            else QualificationStatusEnum.QUALIFIED,
            confidence_score=confidence,
            missing_information=missing,
            next_recommended_question=next_question,
            is_adversarial=is_adversarial,
            customer_sentiment_score=sentiment_score,
        )


class OpenAILLMClient:
    """Production OpenAI adapter with structured output and fallback guard."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout: float = 8.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.fallback = MockRuleBasedLLMClient()

    async def extract_lead_intelligence(
        self,
        conversation_history: list[dict[str, str]],
        existing_lead_data: ExtractedLeadData | None = None,
    ) -> LeadExtractionResult:
        if not self.api_key or self.api_key.startswith("sk-placeholder"):
            return await self.fallback.extract_lead_intelligence(
                conversation_history, existing_lead_data
            )

        # Call OpenAI with JSON schema response format
        prompt = (
            "You are an expert sales intelligence AI. Analyze the customer dialogue and extract "
            "structured B2B qualification attributes strictly matching the JSON schema. "
            "Never invent facts that were not stated."
        )
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Existing data: {existing_lead_data.model_dump_json() if existing_lead_data else '{}'}\nDialogue: {json.dumps(conversation_history)}",
            },
        ]

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "response_format": {"type": "json_object"},
                        "temperature": 0.1,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    return LeadExtractionResult.model_validate_json(content)
        except Exception as exc:
            logger.warning(f"OpenAI API call failed ({exc}); engaging fallback engine")

        return await self.fallback.extract_lead_intelligence(
            conversation_history, existing_lead_data
        )


def get_llm_client() -> LLMClientProtocol:
    """Factory creating configured LLM client instance."""
    if settings.LLM_PROVIDER == "openai":
        return OpenAILLMClient(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
    return MockRuleBasedLLMClient()
