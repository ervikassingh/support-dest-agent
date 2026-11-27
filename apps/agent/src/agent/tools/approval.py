"""Signed approval ids. MCP recomputes the same HMAC and rejects anything else."""

from __future__ import annotations

import hashlib
import hmac

from agent.settings import settings


def approval_id(order_id: str, amount: float) -> str:
    cents = int(round(float(amount) * 100))
    mac = hmac.new(
        settings.approval_secret.encode(),
        f"{order_id}:{cents}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"APR-{mac}"
