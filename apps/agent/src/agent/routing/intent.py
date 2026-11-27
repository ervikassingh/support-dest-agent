"""Intent classifier for cheap vs main routing."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph.state import Intent
from agent.models import get_cheap_model

logger = logging.getLogger(__name__)

_SYSTEM = """Classify the customer support message into exactly one intent.
Return JSON only: {"intent": "<label>", "order_id": "<or null>", "customer_id": "<or null>"}

Labels:
- chitchat: greetings, thanks, small talk, no support task
- policy: return/shipping/account policy questions
- order: order status, tracking, what's in my order
- refund: wants money back / refund / cancel and refund
- email: wants an email sent (confirmation, receipt, written summary)
- out_of_scope: unrelated to this store's support

Extract ORD-#### order ids and CUS-# or CUS-GUEST customer ids when present."""


def _heuristic(text: str) -> Intent:
    lower = text.lower()
    if any(w in lower for w in ("refund", "money back", "return my money")):
        return "refund"
    if any(w in lower for w in ("send me an email", "email me", "email confirmation", "send email")):
        return "email"
    if any(w in lower for w in ("order", "tracking", "shipment", "shipping status", "ord-")):
        return "order"
    if any(w in lower for w in ("policy", "return window", "warranty", "shipping terms")):
        return "policy"
    if any(w in lower for w in ("hello", "hi ", "hey", "thanks", "thank you", "bye")):
        return "chitchat"
    return "policy"


def normalize_order_id(value: Any) -> str:
    if value is None:
        return ""
    match = re.search(r"ORD-\d+", str(value), re.I)
    return match.group(0).upper() if match else ""


def normalize_customer_id(value: Any) -> str:
    """MCP ids are CUS-1 and CUS-GUEST. Accept the old CUST- prefix too."""
    if value is None:
        return ""
    text = re.sub(r"\bCUST-", "CUS-", str(value), flags=re.I)
    match = re.search(r"CUS-(?:GUEST|\d+)", text, re.I)
    return match.group(0).upper() if match else ""


def _extract_ids(text: str) -> tuple[str, str]:
    return normalize_order_id(text), normalize_customer_id(text)


async def classify_intent(messages: list[Any]) -> dict[str, Any]:
    """Classify latest user message. Falls back to heuristics if the LLM fails."""
    last_user = ""
    for msg in reversed(messages):
        content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "")
        role = getattr(msg, "type", None) or (msg.get("role") if isinstance(msg, dict) else "")
        if role in ("human", "user") or getattr(msg, "type", "") == "human":
            last_user = content if isinstance(content, str) else str(content)
            break
    if not last_user and messages:
        last = messages[-1]
        last_user = getattr(last, "content", "") or str(last)

    order_id, customer_id = _extract_ids(last_user)
    try:
        model = get_cheap_model()
        resp = await model.ainvoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=last_user)]
        )
        raw = resp.content if isinstance(resp.content, str) else str(resp.content)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        intent = data.get("intent") or _heuristic(last_user)
        if intent not in {"chitchat", "policy", "order", "refund", "email", "out_of_scope"}:
            intent = _heuristic(last_user)
        return {
            "intent": intent,
            "order_id": normalize_order_id(data.get("order_id")) or order_id,
            "customer_id": normalize_customer_id(data.get("customer_id")) or customer_id,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Intent LLM failed (%s); using heuristics", exc)
        return {
            "intent": _heuristic(last_user),
            "order_id": order_id,
            "customer_id": customer_id,
        }
