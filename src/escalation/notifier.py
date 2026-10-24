"""Team notification dispatcher (Slack / Webhook alerts)."""

from typing import Any

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EscalationNotifier:
    """Dispatches formatted escalation dossiers to human agent communication channels."""

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url or settings.SLACK_WEBHOOK_URL
        # In-memory deduplication set to avoid alert storming
        self._sent_alerts: set[str] = set()

    async def dispatch_slack_alert(
        self,
        incident_id: str,
        phone_number: str,
        reason: str,
        dossier: dict[str, Any],
    ) -> bool:
        """Send a structured Slack escalation card with customer context."""
        # Deduplicate alert per incident
        if incident_id in self._sent_alerts:
            logger.info(f"Duplicate escalation alert suppressed for incident {incident_id}")
            return False

        budget_val = dossier.get("budget") or 0.0
        message_blocks = {
            "text": f"🚨 Human Handoff Alert: {phone_number}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🚨 WhatsApp Customer Escalation",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Phone:*\n{phone_number}"},
                        {"type": "mrkdwn", "text": f"*Trigger Reason:*\n{reason}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Lead Name:*\n{dossier.get('contact_name') or 'Unknown'}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Company:*\n{dossier.get('company_name') or 'Unknown'}",
                        },
                        {"type": "mrkdwn", "text": f"*Budget:*\n${budget_val:,.2f}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Qualification Status:*\n{dossier.get('qualification_status') or 'NEW'}",
                        },
                    ],
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Incident ID: `{incident_id}` | Automation paused",
                        }
                    ],
                },
            ],
        }

        self._sent_alerts.add(incident_id)

        if self.webhook_url and self.webhook_url.startswith("https://hooks.slack.com"):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(self.webhook_url, json=message_blocks)
                    if resp.status_code == 200:
                        logger.info(
                            f"Slack escalation alert dispatched successfully for {incident_id}"
                        )
                        return True
            except Exception as exc:
                logger.error(f"Failed posting Slack escalation alert: {exc}")

        logger.info(
            f"[Escalation Notifier Simulation] Slack card generated for {phone_number}: {reason}"
        )
        return True


# Singleton notifier
notifier = EscalationNotifier()
