"""Customer email send tool — stub provider; requires confirmation_id."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from agent.settings import settings

logger = logging.getLogger(__name__)


def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    confirmation_id: str | None = None,
) -> dict[str, Any]:
    """Send (or stub) an email. Hard-refuses without confirmation_id."""
    if not confirmation_id or not str(confirmation_id).strip():
        return {
            "ok": False,
            "error": "send_email refused: missing confirmation_id. Customer must confirm the draft first.",
        }

    email_id = f"EML-{uuid.uuid4().hex[:8]}"
    payload = {
        "ok": True,
        "email_id": email_id,
        "to": to,
        "subject": subject,
        "body": body,
        "confirmation_id": confirmation_id,
        "provider": settings.email_provider,
        "status": "stubbed" if settings.email_provider == "stub" else "sent",
    }
    logger.info("send_email %s", payload)
    return payload
