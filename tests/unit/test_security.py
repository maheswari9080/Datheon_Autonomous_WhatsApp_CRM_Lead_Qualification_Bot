"""Unit tests for HMAC-SHA256 signature verification and security utilities."""

import pytest
from src.core.exceptions import InvalidWebhookSignatureError
from src.core.logging import mask_pii
from src.core.security import compute_whatsapp_signature, verify_whatsapp_signature

TEST_SECRET = "test_meta_app_secret_12345"
SAMPLE_BODY = b'{"object":"whatsapp_business_account","entry":[{"id":"123","changes":[]}]}'


def test_valid_signature_accepted():
    """Verify that a properly signed payload passes verification."""
    valid_sig = compute_whatsapp_signature(SAMPLE_BODY, TEST_SECRET)
    assert verify_whatsapp_signature(SAMPLE_BODY, valid_sig, TEST_SECRET) is True


def test_missing_signature_rejected():
    """Verify that omitting X-Hub-Signature-256 raises InvalidWebhookSignatureError."""
    with pytest.raises(InvalidWebhookSignatureError) as exc_info:
        verify_whatsapp_signature(SAMPLE_BODY, None, TEST_SECRET)
    assert "Missing X-Hub-Signature-256 header" in str(exc_info.value)


def test_malformed_signature_prefix_rejected():
    """Verify that a signature lacking the 'sha256=' prefix is rejected."""
    raw_hash = "abcdef1234567890"
    with pytest.raises(InvalidWebhookSignatureError) as exc_info:
        verify_whatsapp_signature(SAMPLE_BODY, raw_hash, TEST_SECRET)
    assert "Malformed signature format" in str(exc_info.value)


def test_tampered_payload_rejected():
    """Verify that even a 1-character modification in payload invalidates HMAC."""
    valid_sig = compute_whatsapp_signature(SAMPLE_BODY, TEST_SECRET)
    tampered_body = SAMPLE_BODY.replace(b"123", b"999")

    with pytest.raises(InvalidWebhookSignatureError) as exc_info:
        verify_whatsapp_signature(tampered_body, valid_sig, TEST_SECRET)
    assert "Webhook signature mismatch" in str(exc_info.value)


def test_wrong_secret_rejected():
    """Verify that signature generated with a different secret fails verification."""
    valid_sig = compute_whatsapp_signature(SAMPLE_BODY, "different_secret_key")

    with pytest.raises(InvalidWebhookSignatureError) as exc_info:
        verify_whatsapp_signature(SAMPLE_BODY, valid_sig, TEST_SECRET)
    assert "Webhook signature mismatch" in str(exc_info.value)


def test_pii_masking_in_logs():
    """Verify that PII patterns (phone numbers, bearer tokens, secrets) are redacted."""
    raw_message = "Customer +1-555-123-4567 requested demo with Authorization: Bearer abc12345xyz token: super_secret_pass"
    masked = mask_pii(raw_message)

    assert "+1-555-123-4567" not in masked
    assert "Bearer [REDACTED_TOKEN]" in masked
    assert "token: [REDACTED]" in masked
