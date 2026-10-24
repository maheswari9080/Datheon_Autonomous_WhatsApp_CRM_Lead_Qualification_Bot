"""Meta WhatsApp Cloud API payload parser."""

from dataclasses import dataclass
from typing import Any
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ParsedWhatsAppMessage:
    """Normalized inbound WhatsApp customer message."""

    message_id: str
    sender_phone: str
    contact_name: str | None
    message_type: str  # TEXT, INTERACTIVE_BUTTON, INTERACTIVE_LIST
    text_content: str
    timestamp: int
    raw_payload: dict[str, Any]


@dataclass
class ParsedWhatsAppStatus:
    """Delivery or read status callback from Meta."""

    message_id: str
    recipient_phone: str
    status: str  # sent, delivered, read, failed
    timestamp: int
    error_details: dict[str, Any] | None


class WhatsAppPayloadParser:
    """Extracts typed messages and status events from raw Meta webhook JSON."""

    @classmethod
    def parse_payload(cls, payload: dict[str, Any]) -> tuple[list[ParsedWhatsAppMessage], list[ParsedWhatsAppStatus]]:
        """Parse raw webhook JSON into structured messages and delivery statuses.
        
        Guarantees that delivery/read receipts are completely separated from
        inbound customer messages so status callbacks NEVER accidentally create leads.
        """
        messages: list[ParsedWhatsAppMessage] = []
        statuses: list[ParsedWhatsAppStatus] = []

        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Extract profile contacts if available
                contacts_map: dict[str, str] = {}
                for contact in value.get("contacts", []):
                    wa_id = contact.get("wa_id")
                    profile_name = contact.get("profile", {}).get("name")
                    if wa_id and profile_name:
                        contacts_map[wa_id] = profile_name

                # 1. Parse Inbound Customer Messages
                for msg in value.get("messages", []):
                    msg_id = msg.get("id")
                    sender = msg.get("from")
                    timestamp = int(msg.get("timestamp", 0))
                    msg_type = msg.get("type", "unknown")
                    contact_name = contacts_map.get(sender)

                    text_content = ""
                    normalized_type = "TEXT"

                    if msg_type == "text":
                        text_content = msg.get("text", {}).get("body", "").strip()
                        normalized_type = "TEXT"
                    elif msg_type == "interactive":
                        interactive = msg.get("interactive", {})
                        i_type = interactive.get("type")
                        if i_type == "button_reply":
                            btn = interactive.get("button_reply", {})
                            text_content = btn.get("title", btn.get("id", ""))
                            normalized_type = "INTERACTIVE_BUTTON"
                        elif i_type == "list_reply":
                            lst = interactive.get("list_reply", {})
                            text_content = lst.get("title", lst.get("id", ""))
                            normalized_type = "INTERACTIVE_LIST"
                    elif msg_type == "button":
                        btn = msg.get("button", {})
                        text_content = btn.get("text", btn.get("payload", ""))
                        normalized_type = "INTERACTIVE_BUTTON"
                    else:
                        logger.warning(f"Unsupported WhatsApp message type received: {msg_type}")
                        text_content = f"[{msg_type.upper()} MESSAGE]"
                        normalized_type = msg_type.upper()

                    if msg_id and sender:
                        messages.append(
                            ParsedWhatsAppMessage(
                                message_id=msg_id,
                                sender_phone=sender,
                                contact_name=contact_name,
                                message_type=normalized_type,
                                text_content=text_content,
                                timestamp=timestamp,
                                raw_payload=msg,
                            )
                        )

                # 2. Parse Outbound Message Status Callbacks (sent, delivered, read, failed)
                for st in value.get("statuses", []):
                    st_id = st.get("id")
                    recipient = st.get("recipient_id")
                    status_name = st.get("status")
                    ts = int(st.get("timestamp", 0))
                    errors = st.get("errors")

                    if st_id and recipient and status_name:
                        statuses.append(
                            ParsedWhatsAppStatus(
                                message_id=st_id,
                                recipient_phone=recipient,
                                status=status_name,
                                timestamp=ts,
                                error_details=errors[0] if errors else None,
                            )
                        )

        return messages, statuses
