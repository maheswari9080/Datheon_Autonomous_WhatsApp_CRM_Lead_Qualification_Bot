"""Structured JSON logging with PII masking and correlation tracking."""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Context variable for request correlation IDs across async tasks
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="system")

# PII regex patterns for automated redaction
PHONE_REGEX = re.compile(r"(\+?\d{1,3})[-.\s]?(\d{3})[-.\s]?\d{3}[-.\s]?(\d{2,4})")
BEARER_REGEX = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE)
SECRET_REGEX = re.compile(
    r"(secret|token|key|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{6,})['\"]?", re.IGNORECASE
)


def mask_pii(text: str) -> str:
    """Mask phone numbers, bearer tokens, and secrets in log messages."""
    if not isinstance(text, str):
        return text
    # Mask phone: +1 555 123 4567 -> +1 555 *** 4567
    text = PHONE_REGEX.sub(r"\1 \2 *** \3", text)
    # Mask bearer tokens
    text = BEARER_REGEX.sub(r"\1[REDACTED_TOKEN]", text)
    # Mask secrets
    text = SECRET_REGEX.sub(r"\1: [REDACTED]", text)
    return text


class StructuredJsonFormatter(logging.Formatter):
    """Custom logging formatter outputting single-line structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": mask_pii(record.getMessage()),
            "correlation_id": correlation_id_ctx.get(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include custom extra attributes if present
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            for k, v in record.extra_fields.items():
                if isinstance(v, str):
                    log_payload[k] = mask_pii(v)
                else:
                    log_payload[k] = v

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload, default=str)


def setup_logging(log_level: str = "INFO") -> None:
    """Initialize root logger with StructuredJsonFormatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredJsonFormatter())
    root_logger.addHandler(console_handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Obtain a named logger instance."""
    return logging.getLogger(name)
