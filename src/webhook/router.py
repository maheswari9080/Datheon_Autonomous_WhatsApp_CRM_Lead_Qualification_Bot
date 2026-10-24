"""FastAPI router for Meta WhatsApp Cloud API webhook handshake and event ingestion."""

import json
import uuid
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from src.core.config import get_settings
from src.core.exceptions import InvalidWebhookSignatureError
from src.core.logging import correlation_id_ctx, get_logger
from src.core.security import verify_whatsapp_signature

logger = get_logger(__name__)
settings = get_settings()

webhook_router = APIRouter(prefix="/webhook", tags=["WhatsApp Webhook"])


@webhook_router.get("", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    """Meta WhatsApp Webhook GET Verification Challenge.
    
    Meta sends hub.mode='subscribe', hub.verify_token, and hub.challenge.
    If hub.verify_token matches configured META_VERIFY_TOKEN, return hub.challenge as plain text.
    """
    logger.info(
        "Received webhook verification challenge",
        extra={"extra_fields": {"hub_mode": hub_mode}},
    )

    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        if hub_challenge is not None:
            logger.info("Webhook verification challenge accepted")
            return PlainTextResponse(content=hub_challenge, status_code=status.HTTP_200_OK)

    logger.warning("Webhook verification challenge failed: invalid mode or token")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch or invalid hub.mode",
    )


@webhook_router.post("", status_code=status.HTTP_200_OK)
async def ingest_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> dict[str, str]:
    """Meta WhatsApp Webhook POST Ingestion Endpoint.
    
    1. Validates HMAC-SHA256 signature against raw request body bytes.
    2. Generates a correlation ID for end-to-end event tracing.
    3. Quickly returns 200 OK within 200ms to fulfill Meta SLA.
    4. Enqueues background worker for parsing and conversation pipeline.
    """
    correlation_id = str(uuid.uuid4())
    correlation_id_ctx.set(correlation_id)

    raw_body = await request.body()

    # STRIDE Spoofing & Tampering defense
    try:
        verify_whatsapp_signature(
            payload_bytes=raw_body,
            signature_header=x_hub_signature_256,
            app_secret=settings.META_APP_SECRET,
        )
    except InvalidWebhookSignatureError as exc:
        logger.error(
            f"Webhook signature rejected: {exc.message}",
            extra={"extra_fields": {"correlation_id": correlation_id}},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Signature verification failed: {exc.message}",
        ) from exc

    # Parse JSON payload safely
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        logger.error(
            f"Malformed JSON body in webhook: {exc}",
            extra={"extra_fields": {"correlation_id": correlation_id}},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON body",
        ) from exc

    # Fast ACK: Meta expects 200 OK fast or it retries
    logger.info(
        "Webhook accepted for async processing",
        extra={"extra_fields": {"correlation_id": correlation_id, "object": payload.get("object")}},
    )

    # Note: background worker dispatch hook will be connected in subsequent commit
    return {"status": "received", "correlation_id": correlation_id}
