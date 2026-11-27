"""Email flow: draft → customer confirm interrupt → stub send."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from agent.graph.state import AgentState
from agent.tools.local.send_email import send_email


async def draft_email(state: AgentState) -> dict[str, Any]:
    order_id = state.get("order_id") or ""
    to = "customer@example.com"
    subject = "Your support desk update"
    body = (
        f"Hello,\n\nHere is an update from support"
        f"{f' regarding {order_id}' if order_id else ''}.\n\n"
        "Thank you for contacting us.\n"
    )
    draft = {
        "to": to,
        "subject": subject,
        "body": body,
        "order_id": order_id,
    }
    reply = (
        "I've drafted this email for you:\n\n"
        f"To: {to}\nSubject: {subject}\n\n{body}\n"
        "Reply **yes** to send, or **no** to cancel."
    )
    return {
        "email_draft": draft,
        "interrupt_kind": "email",
        "messages": [AIMessage(content=reply)],
        "final_reply": reply,
    }


async def await_email_confirm(state: AgentState) -> dict[str, Any]:
    draft = state.get("email_draft") or {}
    decision = interrupt({"type": "email_confirm", "draft": draft})
    confirmed = False
    if isinstance(decision, dict):
        confirmed = bool(decision.get("confirmed") or decision.get("decision") == "approve")
    elif isinstance(decision, str):
        confirmed = decision.strip().lower() in {"yes", "y", "confirm", "approve", "send"}
    return {"email_confirmed": confirmed, "approval": decision if isinstance(decision, dict) else {}}


async def send_email_node(state: AgentState) -> dict[str, Any]:
    draft = state.get("email_draft") or {}
    if not state.get("email_confirmed"):
        text = "Okay — I cancelled the email and did not send anything."
        return {
            "messages": [AIMessage(content=text)],
            "final_reply": text,
            "interrupt_kind": "none",
        }

    confirmation_id = f"EMC-{uuid.uuid4().hex[:8]}"
    result = send_email(
        to=str(draft.get("to") or "customer@example.com"),
        subject=str(draft.get("subject") or "Support update"),
        body=str(draft.get("body") or ""),
        confirmation_id=confirmation_id,
    )
    if not result.get("ok"):
        text = f"Email not sent: {result.get('error')}"
    else:
        text = (
            f"Email {result.get('status')} "
            f"(id={result.get('email_id')}, confirmation={confirmation_id})."
        )
    return {
        "messages": [AIMessage(content=text)],
        "final_reply": text,
        "interrupt_kind": "none",
    }
