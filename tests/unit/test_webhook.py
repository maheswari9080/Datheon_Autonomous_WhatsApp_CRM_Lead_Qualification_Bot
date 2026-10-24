"""Unit and integration tests for WhatsApp webhook lifecycle and deduplication."""

import json

import pytest
from httpx import AsyncClient

from src.core.config import get_settings
from src.core.security import compute_whatsapp_signature
from src.webhook.deduplicator import MessageDeduplicator
from src.webhook.parser import WhatsAppPayloadParser

settings = get_settings()


@pytest.mark.asyncio
async def test_get_webhook_verification_success(async_client: AsyncClient):
    """Verify that a valid Meta handshake returns the hub.challenge with 200 OK."""
    challenge = "challenge_code_987654"
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": settings.META_VERIFY_TOKEN,
        "hub.challenge": challenge,
    }
    response = await async_client.get("/webhook", params=params)
    assert response.status_code == 200
    assert response.text == challenge


@pytest.mark.asyncio
async def test_get_webhook_verification_invalid_token(async_client: AsyncClient):
    """Verify that an incorrect verification token is rejected with 403 Forbidden."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_verification_token",
        "hub.challenge": "12345",
    }
    response = await async_client.get("/webhook", params=params)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_post_webhook_valid_signature(async_client: AsyncClient):
    """Verify that a properly signed POST webhook is accepted with 200 OK."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "12345",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "10001"},
                            "contacts": [
                                {"profile": {"name": "Alice Johnson"}, "wa_id": "15551234567"}
                            ],
                            "messages": [
                                {
                                    "from": "15551234567",
                                    "id": "wamid.TEST001",
                                    "timestamp": "1710000000",
                                    "text": {"body": "Hello! I want to automate our CRM"},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_whatsapp_signature(raw_bytes, settings.META_APP_SECRET)

    response = await async_client.post(
        "/webhook",
        content=raw_bytes,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_post_webhook_missing_signature(async_client: AsyncClient):
    """Verify that omitting X-Hub-Signature-256 results in 403 Forbidden."""
    response = await async_client.post("/webhook", json={"test": "payload"})
    assert response.status_code == 403


def test_parser_separates_messages_and_statuses():
    """Verify that WhatsAppPayloadParser segregates customer messages from status receipts."""
    sample_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"profile": {"name": "Bob"}, "wa_id": "19998887777"}],
                            "messages": [
                                {
                                    "from": "19998887777",
                                    "id": "wamid.MSG123",
                                    "timestamp": "1710000010",
                                    "text": {"body": "We need custom software"},
                                    "type": "text",
                                }
                            ],
                            "statuses": [
                                {
                                    "id": "wamid.OLD999",
                                    "recipient_id": "19998887777",
                                    "status": "delivered",
                                    "timestamp": "1710000005",
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    messages, statuses = WhatsAppPayloadParser.parse_payload(sample_payload)
    assert len(messages) == 1
    assert messages[0].message_id == "wamid.MSG123"
    assert messages[0].sender_phone == "19998887777"
    assert messages[0].contact_name == "Bob"
    assert messages[0].text_content == "We need custom software"

    assert len(statuses) == 1
    assert statuses[0].message_id == "wamid.OLD999"
    assert statuses[0].status == "delivered"


def test_deduplicator_lru_cache():
    """Verify in-memory LRU deduplication behavior."""
    dedup = MessageDeduplicator(max_size=3, ttl_seconds=10)

    assert not dedup.is_processed_in_memory("msg_1")
    dedup.mark_processed_in_memory("msg_1")
    assert dedup.is_processed_in_memory("msg_1")

    dedup.mark_processed_in_memory("msg_2")
    dedup.mark_processed_in_memory("msg_3")
    assert dedup.is_processed_in_memory("msg_1")
    assert dedup.is_processed_in_memory("msg_2")
    assert dedup.is_processed_in_memory("msg_3")

    # Overflow size=3 by adding msg_4
    dedup.mark_processed_in_memory("msg_4")
    # msg_1 should be evicted as oldest
    assert not dedup.is_processed_in_memory("msg_1")
    assert dedup.is_processed_in_memory("msg_4")
