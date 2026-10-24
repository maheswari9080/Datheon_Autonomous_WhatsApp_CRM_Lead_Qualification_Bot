"""Security module: Meta WhatsApp HMAC-SHA256 signature validation and cryptographic defenses."""

import hashlib
import hmac
from src.core.exceptions import InvalidWebhookSignatureError
from src.core.logging import get_logger

logger = get_logger(__name__)


def compute_whatsapp_signature(payload_bytes: bytes, app_secret: str) -> str:
    """Compute Meta-compatible HMAC-SHA256 signature with sha256= prefix.
    
    Args:
        payload_bytes: Exact raw body bytes from HTTP request.
        app_secret: Meta application secret key.
        
    Returns:
        String in format 'sha256=<hex_digest>'.
    """
    key = app_secret.encode("utf-8") if isinstance(app_secret, str) else app_secret
    signature = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={signature}"


def verify_whatsapp_signature(payload_bytes: bytes, signature_header: str | None, app_secret: str) -> bool:
    """Verify that inbound HTTP POST payload originates from Meta WhatsApp Cloud API.
    
    Uses hmac.compare_digest for constant-time comparison to prevent timing side-channel attacks.
    
    Args:
        payload_bytes: Raw HTTP request body bytes.
        signature_header: Raw value of the X-Hub-Signature-256 header.
        app_secret: Meta application secret key.
        
    Returns:
        True if signature is valid.
        
    Raises:
        InvalidWebhookSignatureError: If signature header is missing, malformed, or invalid.
    """
    if not signature_header:
        logger.warning("Rejected webhook: Missing X-Hub-Signature-256 header")
        raise InvalidWebhookSignatureError("Missing X-Hub-Signature-256 header")

    if not signature_header.startswith("sha256="):
        logger.warning("Rejected webhook: Malformed signature header (missing sha256= prefix)")
        raise InvalidWebhookSignatureError("Malformed signature format: expected sha256=<digest>")

    expected_signature = compute_whatsapp_signature(payload_bytes, app_secret)

    # Constant-time comparison defends against timing attacks (STRIDE: Spoofing & Tampering)
    is_valid = hmac.compare_digest(expected_signature, signature_header)

    if not is_valid:
        logger.warning("Rejected webhook: Signature mismatch (possible payload tampering or invalid secret)")
        raise InvalidWebhookSignatureError("Webhook signature mismatch")

    return True
